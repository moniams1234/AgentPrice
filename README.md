# Monitor cen surowców opakowaniowych

Agent AI, który śledzi komunikaty prasowe producentów papieru/tektury/tworzyw,
wyciąga z nich dane o zmianach cen (kwota, region, data wejścia w życie),
zapisuje je w bazie i wysyła alerty przy istotnych zmianach.

## Struktura projektu

```
packaging_price_agent/
├── scraper.py             # pobieranie komunikatów prasowych (RSS) + proxy kosztowe
├── extraction_agent.py    # agent AI: tekst → ustrukturyzowany JSON (Claude API)
├── database.py             # SQLite: zapis i odczyt sygnałów cenowych
├── alerts.py               # reguły alertowania + wysyłka e-mail/Slack
├── main.py                 # orkiestrator — spina wszystko w jeden pipeline
├── dashboard.py             # dashboard Streamlit do przeglądania danych
├── requirements.txt
└── .github/workflows/daily_run.yml   # automatyczne codzienne uruchamianie
```

## Szybki start (lokalnie)

```bash
cd packaging_price_agent
pip install -r requirements.txt --break-system-packages

export ANTHROPIC_API_KEY="twoj_klucz"

# jednorazowe uruchomienie pipeline'u
python main.py

# dashboard
streamlit run dashboard.py
```

## Konfiguracja powiadomień (opcjonalnie)

Zmienne środowiskowe:

| Zmienna | Do czego służy |
|---|---|
| `ANTHROPIC_API_KEY` | wymagana — klucz do agenta ekstrakcyjnego |
| `SLACK_WEBHOOK_URL` | opcjonalna — alerty na Slacka (Incoming Webhook) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_TO` | opcjonalne — alerty e-mail |
| `ALERT_THRESHOLD_PCT` | próg zmiany % wywołujący alert (domyślnie 3) |

## Automatyzacja przez GitHub Actions

1. Wrzuć cały folder do repozytorium GitHub.
2. W ustawieniach repo: **Settings → Secrets and variables → Actions** dodaj
   sekrety: `ANTHROPIC_API_KEY` (wymagany) oraz opcjonalnie `SLACK_WEBHOOK_URL`
   / dane SMTP.
3. Workflow w `.github/workflows/daily_run.yml` uruchomi się automatycznie
   codziennie o 6:00 UTC — możesz też odpalić go ręcznie z zakładki **Actions**.

## Rozbudowa

- **Więcej źródeł**: dopisz kolejne RSS w `scraper.py` (`RSS_SOURCES`) lub
  dodaj płatne API (FOEX, ICIS) jako kolejną funkcję pobierającą.
- **Precyzyjniejszy wpływ na marżę**: uzupełnij `MATERIAL_COST_SHARE`
  w `main.py` rzeczywistymi udziałami kosztowymi z Twoich kalkulacji.
- **Baza w chmurze**: zamień SQLite na PostgreSQL, jeśli projekt urośnie
  (zmiana tylko w `database.py`).
