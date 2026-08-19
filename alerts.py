"""
Silnik alertów — decyduje, czy sygnał cenowy jest wart zgłoszenia,
i wysyła powiadomienie (e-mail i/lub Slack webhook).
"""

import os
import smtplib
from email.mime.text import MIMEText

import requests

ALERT_THRESHOLD_PCT = float(os.environ.get("ALERT_THRESHOLD_PCT", "3"))


def should_alert(signal, threshold_pct: float = ALERT_THRESHOLD_PCT) -> bool:
    """Prosta reguła: alertuj gdy zmiana >= progu ORAZ pewność ekstrakcji high/medium."""
    if signal.confidence == "low":
        return False
    if signal.unit == "procent" and signal.amount is not None:
        return signal.amount >= threshold_pct
    # dla kwot w EUR/t bez znanej ceny bazowej — zawsze alertuj z niższą pewnością
    return signal.confidence == "high"


def format_alert_message(signal, margin_note: str | None = None) -> str:
    kierunek = "🔺 podwyżka" if signal.change_type == "podwyzka" else "🔻 obniżka"
    kwota = f"{signal.amount} {signal.unit}" if signal.amount else "brak danych o kwocie"
    lines = [
        f"{kierunek} — {signal.material}"
        + (f" ({signal.material_detail})" if signal.material_detail else ""),
        f"Zmiana: {kwota}",
        f"Region: {signal.region or 'nie podano'}",
        f"Wejście w życie: {signal.effective_date or 'nie podano'}",
        f"Źródło: {signal.source_company or 'nieznane'}",
        f"Podsumowanie: {signal.summary_pl}",
    ]
    if margin_note:
        lines.append(f"Wpływ na marżę: {margin_note}")
    return "\n".join(lines)


def send_email_alert(subject: str, body: str, to_addr: str) -> None:
    """
    Wysyła e-mail przez SMTP. Wymaga zmiennych środowiskowych:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
    """
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)


def send_slack_alert(message: str) -> None:
    """Wysyła wiadomość na Slacka przez Incoming Webhook. Wymaga SLACK_WEBHOOK_URL."""
    webhook_url = os.environ["SLACK_WEBHOOK_URL"]
    resp = requests.post(webhook_url, json={"text": message}, timeout=10)
    resp.raise_for_status()


if __name__ == "__main__":
    # szybki test formatowania bez faktycznego wysyłania
    from extraction_agent import PriceSignal

    test_signal = PriceSignal(
        material="tektura",
        material_detail="kraftliner",
        change_type="podwyzka",
        amount=35,
        unit="EUR/t",
        currency="EUR",
        region="CEE",
        effective_date="2026-09-01",
        announcement_date="2026-08-15",
        source_company="Stora Enso",
        confidence="high",
        summary_pl="Stora Enso podnosi ceny kraftlinera o 35 EUR/t w regionie CEE od 1 września.",
    )
    print(format_alert_message(test_signal))
    print("\nAlert wysłany?:", should_alert(test_signal))
