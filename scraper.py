"""
Warstwa pobierania — źródła komunikatów prasowych producentów opakowań/papieru
oraz proxy kosztowe (ropa/gaz przez yfinance).

Uwaga: adresy RSS/URL poniżej to przykładowe punkty startowe — producenci
zmieniają struktury stron, więc listę źródeł trzeba okresowo weryfikować
i dostosowywać selektory w `scrape_press_page`.
"""

from __future__ import annotations

import feedparser
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PriceMonitorBot/1.0)"}

# Przykładowe źródła RSS z komunikatami prasowymi producentów papieru/tektury.
# Dodaj/zmień w zależności od dostępności feedów.
RSS_SOURCES = {
    "Stora Enso": "https://www.storaenso.com/en/newsroom/rss",
    "Mondi": "https://www.mondigroup.com/en/media/press-releases/rss/",
    "Smurfit WestRock": "https://www.smurfitwestrock.com/newsroom/rss",
}


def fetch_rss_headlines(source_name: str, url: str, max_items: int = 5) -> list[dict]:
    """Pobiera najnowsze wpisy z danego RSS. Zwraca listę {title, summary, link, published}."""
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"[{source_name}] błąd pobierania RSS: {e}")
        return []

    items = []
    for entry in feed.entries[:max_items]:
        items.append(
            {
                "source": source_name,
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
            }
        )
    return items


def fetch_all_rss() -> list[dict]:
    all_items = []
    for name, url in RSS_SOURCES.items():
        all_items.extend(fetch_rss_headlines(name, url))
    return all_items


def scrape_press_page(url: str) -> str:
    """
    Pobiera pełną treść strony komunikatu (gdy RSS daje tylko skrót).
    Zwraca oczyszczony tekst — do przekazania agentowi ekstrakcyjnemu.
    """
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    return text[:6000]  # limit długości przekazywanej do agenta


def fetch_commodity_proxies() -> dict:
    """
    Pobiera ceny ropy/gazu jako proxy kosztowe (yfinance).
    Zwraca ostatnie ceny zamknięcia.
    """
    import yfinance as yf

    tickers = {"ropa_brent": "BZ=F", "gaz_ziemny": "NG=F"}
    results = {}
    for label, ticker in tickers.items():
        try:
            data = yf.Ticker(ticker).history(period="5d")
            if not data.empty:
                results[label] = round(float(data["Close"].iloc[-1]), 2)
        except Exception as e:
            print(f"Błąd pobierania {ticker}: {e}")
    return results


if __name__ == "__main__":
    print("=== Komunikaty prasowe (RSS) ===")
    for item in fetch_all_rss():
        print(f"[{item['source']}] {item['title']}")

    print("\n=== Proxy kosztowe (ropa/gaz) ===")
    print(fetch_commodity_proxies())
