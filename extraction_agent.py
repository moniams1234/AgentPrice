"""
Agent ekstrakcyjny — przyjmuje nieustrukturyzowany tekst (komunikat prasowy,
e-mail, fragment raportu) o zmianie ceny surowca i zwraca ustrukturyzowany
sygnał cenowy.

Używa OpenRouter (https://openrouter.ai) — jednego klucza API dającego dostęp
do wielu modeli (OpenAI, Anthropic, Google, Meta itd.) przez interfejs
kompatybilny z OpenAI SDK.

Wymaga zmiennej środowiskowej OPENROUTER_API_KEY.
Klucz: https://openrouter.ai/keys (wymaga doładowania konta kredytami).
"""

import json
import os
from dataclasses import dataclass
from datetime import date

from openai import OpenAI

from database import log_token_usage

# Pełna lista modeli i cen: https://openrouter.ai/models
# Przykłady: "openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet",
#            "google/gemini-2.0-flash-001", "meta-llama/llama-3.3-70b-instruct"
MODEL = "openai/gpt-4o-mini"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

SYSTEM_PROMPT = """Jesteś agentem ekstrakcyjnym analizującym komunikaty rynkowe
dotyczące cen surowców opakowaniowych (celuloza, tektura, papier, tworzywa
sztuczne: PE/PP/PET).

Z podanego tekstu wyciągnij WYŁĄCZNIE informacje faktycznie w nim zawarte.
Jeśli jakiejś informacji brak, użyj null — nigdy nie zgaduj i nie wymyślaj
wartości. Jeśli tekst NIE dotyczy zmiany ceny surowca opakowaniowego,
ustaw pole "not_relevant" na true, a resztę pól na null.

Zwróć TYLKO poprawny JSON (bez markdown, bez komentarzy, bez preambuły)
w formacie:

{
  "not_relevant": <true|false>,
  "material": "celuloza|tektura|papier|PE|PP|PET|inne|null",
  "material_detail": "np. NBSK, testliner, kraftliner (jeśli podano) lub null",
  "change_type": "podwyzka|obnizka|utrzymanie|null",
  "amount": <liczba lub null>,
  "unit": "EUR/t|USD/t|PLN/t|procent|null",
  "currency": "EUR|USD|PLN|null",
  "region": "np. CEE, Europa Zachodnia, Polska (jeśli podano) lub null",
  "effective_date": "YYYY-MM-DD lub null",
  "announcement_date": "YYYY-MM-DD lub null",
  "source_company": "nazwa firmy publikującej komunikat (jeśli podano) lub null",
  "confidence": "high|medium|low",
  "summary_pl": "jednozdaniowe podsumowanie po polsku"
}"""


@dataclass
class PriceSignal:
    material: str
    material_detail: str | None
    change_type: str
    amount: float | None
    unit: str | None
    currency: str | None
    region: str | None
    effective_date: str | None
    announcement_date: str | None
    source_company: str | None
    confidence: str
    summary_pl: str
    extracted_on: str = str(date.today())


def _clean_json_response(raw_output: str) -> str:
    """Niektóre modele na OpenRouter (np. Llama) nie respektują response_format
    równie ściśle jak GPT — usuwamy ewentualne ```json ogrodzenia dla pewności."""
    raw_output = raw_output.strip()
    if raw_output.startswith("```"):
        raw_output = raw_output.strip("`")
        if raw_output.startswith("json\n"):
            raw_output = raw_output[5:]
    return raw_output


def extract_price_signal(
    raw_text: str, process_name: str = "ekstrakcja_automatyczna"
) -> PriceSignal | None:
    """Zwraca PriceSignal albo None jeśli tekst nie dotyczy zmiany ceny surowca.

    process_name: etykieta czynności do panelu zużycia tokenów, np.
    "ekstrakcja_automatyczna" (pipeline RSS) albo "ekstrakcja_reczna"
    (wklejony tekst w dashboardzie).
    """
    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=os.environ["OPENROUTER_API_KEY"],
    )

    response = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        max_tokens=500,
        temperature=0,
        extra_headers={
            # opcjonalne, ale zalecane przez OpenRouter do statystyk/rankingów
            "HTTP-Referer": "https://github.com/moniams1234/AgentPrice",
            "X-Title": "AgentPrice",
        },
    )

    _log_usage(response, process_name)

    raw_output = _clean_json_response(response.choices[0].message.content)
    data = json.loads(raw_output)

    if data.get("not_relevant"):
        return None

    data.pop("not_relevant", None)
    return PriceSignal(**data)


def _log_usage(response, process_name: str) -> None:
    """Zapisuje zużycie tokenów z odpowiedzi API do bazy danych.

    Tokeny "myślenia" (reasoning) dotyczą modeli typu o1/o3 lub
    DeepSeek-R1 dostępnych przez OpenRouter — dla zwykłych modeli
    (np. gpt-4o-mini) to pole będzie równe 0.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return

    reasoning_tokens = 0
    details = getattr(usage, "completion_tokens_details", None)
    if details is not None:
        reasoning_tokens = getattr(details, "reasoning_tokens", 0) or 0

    try:
        log_token_usage(
            process=process_name,
            model=response.model or MODEL,
            input_tokens=usage.prompt_tokens or 0,
            output_tokens=usage.completion_tokens or 0,
            reasoning_tokens=reasoning_tokens,
        )
    except Exception as e:
        # logowanie zużycia nie powinno nigdy przerwać głównego zadania
        print(f"Ostrzeżenie: nie udało się zalogować zużycia tokenów: {e}")


def assess_margin_impact(signal: PriceSignal, material_cost_share_pct: float) -> str:
    """
    Drugi, analityczny krok agenta: ocena wpływu zmiany ceny surowca na marżę
    produktu finalnego, jeśli znamy udział surowca w koszcie wytworzenia.

    material_cost_share_pct: np. 60 oznacza, że dany surowiec stanowi 60%
    kosztu wytworzenia produktu (np. celuloza w tekturze).
    """
    if signal.amount is None or signal.unit != "procent":
        return (
            "Brak wystarczających danych do przeliczenia wpływu na marżę "
            "(potrzebna zmiana w %, nie w EUR/t bez znajomości bazowej ceny)."
        )

    change_pct = signal.amount if signal.change_type == "podwyzka" else -signal.amount
    margin_impact_pct = change_pct * (material_cost_share_pct / 100)

    direction = "wzrost kosztu" if margin_impact_pct > 0 else "spadek kosztu"
    return (
        f"Przy udziale surowca {material_cost_share_pct}% w koszcie wytworzenia: "
        f"{direction} o ok. {abs(margin_impact_pct):.1f} p.p. marży, jeśli cena "
        f"sprzedaży nie zostanie skorygowana."
    )


if __name__ == "__main__":
    example_text = """
    Komunikat prasowy — Stora Enso, 15 sierpnia 2026

    Stora Enso informuje o podwyżce cen kraftlinera o 35 EUR/tonę
    w regionie Europy Środkowo-Wschodniej. Nowe ceny wejdą w życie
    od 1 września 2026 roku i są odpowiedzią na rosnące koszty
    energii oraz celulozy w regionie.
    """
    signal = extract_price_signal(example_text)
    if signal:
        from dataclasses import asdict
        print(json.dumps(asdict(signal), indent=2, ensure_ascii=False))
    else:
        print("Tekst nie dotyczy zmiany ceny surowca.")
