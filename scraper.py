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

# Działające kanały RSS z komunikatami o papierze, tekturze i opakowaniach.
# Zweryfikowane 2026-08-19. PR Newswire pokrywa m.in. Stora Enso, Mondi,
# Smurfit WestRock, International Paper, Graphic Packaging, Cascades i innych
# producentów, gdy publikują komunikaty przez tę sieć dystrybucji.
RSS_SOURCES = {
    "PR Newswire - Paper & Packaging": "https://www.prnewswire.com/rss/heavy-industry-manufacturing-latest-news/paper-forest-products-containers-list.rss",
}

# Prosty filtr słów kluczowych stosowany PRZED wysłaniem tekstu do agenta AI —
# oszczędza tokeny, pomijając komunikaty spoza tematyki cen surowców
# (np. ogłoszenia personalne, dywidendy, nagrody).
PRICE_KEYWORDS = [
    "price", "pricing", "increase", "raise", "cost", "surcharge",
    "cena", "podwyżk", "wzrost cen",
]


def is_potentially_price_related(text: str) -> bool:
    """Szybki, tani filtr przed wywołaniem kosztownego agenta AI."""
    lowered = text.lower()
    return any(kw in lowered for kw in PRICE_KEYWORDS)


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
        items = fetch_rss_headlines(name, url)
        if not items:
            print(f"[{name}] RSS zwrócił 0 wpisów, próbuję pobrać stronę HTML jako zapasowe źródło...")
            items = fetch_headlines_from_html_fallback(name)
        all_items.extend(items)
    return all_items


# Zapasowe źródło, gdy adres RSS przestanie działać: strona kategorii
# "Paper, Forest Products & Containers" na PR Newswire, scrapowana bezpośrednio.
FALLBACK_CATEGORY_URL = "https://www.prnewswire.com/news-releases/heavy-industry-manufacturing-latest-news/paper-forest-products-containers-list/"


def fetch_headlines_from_html_fallback(source_name: str, max_items: int = 15) -> list[dict]:
    """Scrapuje nagłówki i linki bezpośrednio ze strony kategorii, gdy RSS nie działa."""
    try:
        resp = requests.get(FALLBACK_CATEGORY_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Błąd pobierania zapasowej strony HTML: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = []
    for link in soup.select("a[href*='/news-releases/']"):
        href = link.get("href", "")
        title = link.get_text(strip=True)
        if not title or len(title) < 15 or "/news-releases/" not in href:
            continue
        full_url = href if href.startswith("http") else f"https://www.prnewswire.com{href}"
        items.append(
            {
                "source": source_name,
                "title": title,
                "summary": "",  # pusty skrót wymusi pobranie pełnej treści w main.py
                "link": full_url,
                "published": "",
            }
        )
        if len(items) >= max_items:
            break
    return items


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
