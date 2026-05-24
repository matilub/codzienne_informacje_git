"""
Codzienny digest newsów — RSS + Groq API (darmowy) + ntfy.sh
Tematy: Technologia i AI, Nauka i zdrowie, Kultura i rozrywka
"""

import urllib.request
import urllib.parse
import json
import os
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone, timedelta

# ── Konfiguracja ──────────────────────────────────────────────────────────────

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "gsk_...")
NTFY_TOPIC   = os.environ.get("NTFY_TOPIC", "moj-digest-XYZ123")
NTFY_SERVER  = "https://ntfy.sh"

# Źródła RSS dla każdego tematu
RSS_FEEDS = {
    "tech": [
        "https://feeds.feedburner.com/TechCrunch",
        "https://www.theverge.com/rss/index.xml",
        "https://hnrss.org/frontpage",                # Hacker News
    ],
    "nauka": [
        "https://www.sciencedaily.com/rss/top/science.xml",
        "https://www.newscientist.com/feed/home/",
        "https://feeds.nature.com/nature/rss/current",
    ],
    "kultura": [
        "https://pitchfork.com/feed/the-pitch/rss",
        "https://deadline.com/feed/",
        "https://www.theguardian.com/culture/rss",
    ],
}

MAX_ITEMS_PER_FEED = 5   # ile ostatnich artykułów pobieramy z każdego feedu
MAX_AGE_HOURS      = 48  # pomijamy artykuły starsze niż N godzin


# ── Pobieranie i parsowanie RSS ───────────────────────────────────────────────

def fetch_rss(url: str) -> list[dict]:
    """Pobiera feed RSS i zwraca listę {title, description, link, date}."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (digest-bot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        root = ET.fromstring(data)
    except Exception as e:
        print(f"  ⚠ Błąd RSS {url}: {e}")
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)

    # Obsługa zarówno RSS 2.0 jak i Atom
    entries = root.findall(".//item") or root.findall(".//atom:entry", ns)

    for entry in entries[:MAX_ITEMS_PER_FEED]:
        title = (
            entry.findtext("title")
            or entry.findtext("atom:title", namespaces=ns)
            or ""
        ).strip()
        desc = (
            entry.findtext("description")
            or entry.findtext("atom:summary", namespaces=ns)
            or ""
        ).strip()
        link = (
            entry.findtext("link")
            or (entry.find("atom:link", ns).get("href") if entry.find("atom:link", ns) is not None else "")
        ).strip()

        # Usuwamy tagi HTML z opisu
        import re
        desc = re.sub(r"<[^>]+>", "", desc)[:300]

        items.append({"title": title, "description": desc, "link": link})

    return items


def collect_headlines() -> dict[str, list[dict]]:
    result = {}
    for category, urls in RSS_FEEDS.items():
        print(f"  Pobieram RSS: {category}...")
        items = []
        for url in urls:
            items.extend(fetch_rss(url))
        result[category] = items[:12]  # maks. 12 nagłówków per kategoria do Groq
    return result


# ── Streszczenie przez Groq ───────────────────────────────────────────────────

def summarize_with_groq(headlines: dict[str, list[dict]]) -> str:
    today = date.today().strftime("%d %B %Y")

    # Budujemy blok tekstu z nagłówkami
    sections = []
    labels = {
        "tech":    "TECHNOLOGIA I AI",
        "nauka":   "NAUKA I ZDROWIE",
        "kultura": "KULTURA I ROZRYWKA",
    }
    for cat, items in headlines.items():
        section = f"### {labels[cat]}\n"
        for item in items:
            section += f"- {item['title']}: {item['description']}\n"
        sections.append(section)

    raw_headlines = "\n".join(sections)

    prompt = f"""Dzisiaj jest {today}. Poniżej masz surowe nagłówki z serwisów informacyjnych z ostatnich 48 godzin.

{raw_headlines}

Na ich podstawie przygotuj krótki, ciekawy poranny digest po polsku. Dla każdej kategorii wybierz 2-3 NAJCIEKAWSZE i NAJWAŻNIEJSZE informacje. Streszczaj zwięźle i po polsku — 1-2 zdania na punkt. Pomiń nudne lub mało istotne rzeczy.

Formatuj DOKŁADNIE tak (bez żadnego dodatkowego tekstu przed ani po):

📱 TECH & AI
• [info 1]
• [info 2]

🔬 NAUKA & ZDROWIE
• [info 1]
• [info 2]

🎬 KULTURA & ROZRYWKA
• [info 1]
• [info 2]

Dobrego dnia!"""

    data = json.dumps({
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "Jesteś redaktorem który przygotowuje zwięzłe, ciekawe podsumowania newsów po polsku. Piszesz konkretnie i bez lania wody."
            },
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1024,
        "temperature": 0.4,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())

    return result["choices"][0]["message"]["content"].strip()


# ── Wysyłka przez ntfy.sh ─────────────────────────────────────────────────────

def send_notification(body: str) -> None:
    today = date.today().strftime("%d.%m.%Y")
    title = f"☀️ Poranny digest — {today}"

    data = json.dumps({
        "topic":    NTFY_TOPIC,
        "title":    title,
        "message":  body,
        "priority": 3,
        "tags":     ["newspaper"],
    }).encode("utf-8")

    req = urllib.request.Request(
        NTFY_SERVER,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        print(f"ntfy.sh → HTTP {resp.status}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Pobieram nagłówki RSS...")
    headlines = collect_headlines()

    print("Streszczam przez Groq...")
    digest = summarize_with_groq(headlines)

    print("─" * 50)
    print(digest)
    print("─" * 50)

    print("Wysyłam powiadomienie...")
    send_notification(digest)
    print("Gotowe! ✓")


if __name__ == "__main__":
    main()
