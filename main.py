"""
Główny orkiestrator — uruchamiany codziennie (cron / GitHub Actions).

Przepływ:
1. Pobierz najnowsze komunikaty prasowe (RSS) + proxy kosztowe.
2. Dla każdego komunikatu: wywołaj agenta ekstrakcyjnego.
3. Zapisz nowe sygnały do bazy (pomijając duplikaty).
4. Dla sygnałów spełniających regułę alertu: wyślij powiadomienie.
"""

import os

from alerts import format_alert_message, send_email_alert, send_slack_alert, should_alert
from database import init_db, insert_signal, log_alert
from extraction_agent import extract_price_signal
from scraper import fetch_all_rss, scrape_press_page

# Udział poszczególnych surowców w koszcie wytworzenia — dostosuj do własnych danych
MATERIAL_COST_SHARE = {
    "celuloza": 55,
    "tektura": 40,
    "papier": 45,
    "PE": 60,
    "PP": 60,
    "PET": 60,
}


def run_pipeline(notify: bool = True) -> None:
    init_db()

    headlines = fetch_all_rss()
    print(f"Pobrano {len(headlines)} komunikatów z RSS.")

    new_signals = []

    for item in headlines:
        # Jeśli RSS daje tylko skrót, pobierz pełną treść strony
        text_to_analyze = item["summary"]
        if item["link"] and len(text_to_analyze) < 200:
            try:
                text_to_analyze = scrape_press_page(item["link"])
            except Exception as e:
                print(f"Nie udało się pobrać pełnej treści {item['link']}: {e}")

        full_text = f"{item['title']}\n\n{text_to_analyze}"

        try:
            signal = extract_price_signal(full_text)
        except Exception as e:
            print(f"Błąd ekstrakcji dla '{item['title']}': {e}")
            continue

        if signal is None:
            continue  # komunikat nie dotyczył zmiany ceny surowca

        signal_id = insert_signal(signal, source_url=item["link"])
        if signal_id is None:
            continue  # duplikat, już mamy ten sygnał w bazie

        print(f"Nowy sygnał zapisany (id={signal_id}): {signal.summary_pl}")
        new_signals.append((signal_id, signal))

    if notify:
        for signal_id, signal in new_signals:
            if should_alert(signal):
                message = format_alert_message(signal)
                _dispatch_alert(signal_id, message)

    print(f"\nZakończono. Nowych sygnałów: {len(new_signals)}.")


def _dispatch_alert(signal_id: int, message: str) -> None:
    sent_any = False

    if os.environ.get("SLACK_WEBHOOK_URL"):
        try:
            send_slack_alert(message)
            log_alert(signal_id, message, channel="slack")
            sent_any = True
        except Exception as e:
            print(f"Błąd wysyłki Slack: {e}")

    if os.environ.get("SMTP_HOST") and os.environ.get("ALERT_EMAIL_TO"):
        try:
            send_email_alert(
                subject="Alert cenowy — surowce opakowaniowe",
                body=message,
                to_addr=os.environ["ALERT_EMAIL_TO"],
            )
            log_alert(signal_id, message, channel="email")
            sent_any = True
        except Exception as e:
            print(f"Błąd wysyłki e-mail: {e}")

    if not sent_any:
        print("Uwaga: brak skonfigurowanego kanału powiadomień (Slack/e-mail).")


if __name__ == "__main__":
    run_pipeline()
