"""
Agent ekstrakcyjny do analizy cen surowców opakowaniowych.

Zadanie: przyjmuje nieustrukturyzowany tekst (komunikat prasowy, e-mail,
fragment raportu) o zmianie ceny surowca i zwraca ustrukturyzowany JSON
gotowy do zapisu w bazie danych.

Wymaga:
    pip install anthropic --break-system-packages

Wymaga zmiennej środowiskowej ANTHROPIC_API_KEY (klucz z Twojego konta
Anthropic — dostępny w console.anthropic.com/settings/keys).
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import date

import anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """Jesteś agentem ekstrakcyjnym analizującym komunikaty rynkowe
dotyczące cen surowców opakowaniowych (celuloza, tektura, papier, tworzywa
sztuczne: PE/PP/PET).

Z podanego tekstu wyciągnij WYŁĄCZNIE informacje faktycznie w nim zawarte.
Jeśli jakiejś informacji brak, użyj null — nigdy nie zgaduj i nie wymyślaj
wartości.

Zwróć TYLKO poprawny JSON (bez markdown, bez komentarzy, bez preambuły)
w formacie:

{
  "material": "celuloza|tektura|papier|PE|PP|PET|inne",
  "material_detail": "np. NBSK, testliner, kraftliner (jeśli podano)",
  "change_type": "podwyzka|obnizka|utrzymanie",
  "amount": <liczba lub null>,
  "unit": "EUR/t|USD/t|PLN/t|procent|null",
  "currency": "EUR|USD|PLN|null",
  "region": "np. CEE, Europa Zachodnia, Polska (jeśli podano)",
  "effective_date": "YYYY-MM-DD lub null",
  "announcement_date": "YYYY-MM-DD lub null",
  "source_company": "nazwa firmy publikującej komunikat (jeśli podano)",
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


def extract_price_signal(raw_text: str) -> PriceSignal:
    """Wysyła surowy tekst komunikatu do Claude i zwraca ustrukturyzowany sygnał cenowy."""
    client = anthropic.Anthropic()  # klucz brany z ANTHROPIC_API_KEY

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": raw_text}],
    )

    raw_output = response.content[0].text.strip()

    # zabezpieczenie na wypadek, gdyby model dodał ```json mimo instrukcji
    if raw_output.startswith("```"):
        raw_output = raw_output.strip("`")
        raw_output = raw_output.replace("json\n", "", 1)

    data = json.loads(raw_output)
    return PriceSignal(**data)


def save_to_jsonl(signal: PriceSignal, path: str = "price_signals.jsonl") -> None:
    """Dopisuje sygnał do lokalnego pliku JSONL (prosty magazyn zanim wdrożysz bazę SQL)."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(signal), ensure_ascii=False) + "\n")


if __name__ == "__main__":
    # --- przykładowy test na fikcyjnym komunikacie ---
    example_text = """
    Komunikat prasowy — Stora Enso, 15 sierpnia 2026

    Stora Enso informuje o podwyżce cen kraftlinera o 35 EUR/tonę
    w regionie Europy Środkowo-Wschodniej. Nowe ceny wejdą w życie
    od 1 września 2026 roku i są odpowiedzią na rosnące koszty
    energii oraz celulozy w regionie.
    """

    print("Wysyłanie komunikatu do agenta ekstrakcyjnego...\n")
    signal = extract_price_signal(example_text)

    print("Wynik ekstrakcji:")
    print(json.dumps(asdict(signal), indent=2, ensure_ascii=False))

    save_to_jsonl(signal)
    print("\nZapisano do price_signals.jsonl")
