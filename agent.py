"""
Codzienny digest newsów — RSS + Groq API (darmowy) + ntfy.sh
Spersonalizowany pod: AI/automatyka/robotyka, tech, kawa, polityka, Trójmiasto/Gdańsk, PG
"""

import urllib.request
import json
import os
import re
import xml.etree.ElementTree as ET
import http.client
import ssl
from datetime import date, datetime, timezone, timedelta

# ── Konfiguracja ──────────────────────────────────────────────────────────────

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "gsk_...")
NTFY_TOPIC   = os.environ.get("NTFY_TOPIC", "moj-digest-XYZ123")
NTFY_SERVER  = "https://ntfy.sh"

RSS_FEEDS = {
    "ai_robotyka": [
        "https://feeds.feedburner.com/AIWeekly",
        "https://hnrss.org/frontpage",                          # Hacker News
        "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "https://spectrum.ieee.org/feeds/topic/robotics.rss",   # IEEE Robotics
        "https://spectrum.ieee.org/feeds/topic/automation.rss", # IEEE Automation
        "https://techcrunch.com/category/artificial-intelligence/feed/",
    ],
    "tech": [
        "https://www.theverge.com/rss/index.xml",
        "https://www.wired.com/feed/rss",
        "https://feeds.arstechnica.com/arstechnica/index",
    ],
    "kawa": [
        "https://sprudge.com/feed",               # największy serwis o kawie na świecie
        "https://www.europeancoffeetrip.com/feed/",
    ],
    "polityka": [
        "https://www.politico.eu/feed/",
        "https://feeds.bbci.co.uk/news/world/europe/rss.xml",
    ],
    "trojmiasto": [
        "https://www.trojmiasto.pl/rss/news.xml",
        "https://gdansk.pl/rss.xml",
        "https://www.dziennikbaltycki.pl/rss/articles.xml",
    ],
}

MAX_ITEMS_PER_FEED = 5
MAX_AGE_HOURS      = 48


# ── Pobieranie i parsowanie RSS ───────────────────────────────────────────────

def fetch_rss(url: str) -> list[dict]:
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
    entries = root.findall(".//item") or root.findall(".//atom:entry", ns)
    items = []

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
        desc = re.sub(r"<[^>]+>", "", desc)[:300]
        items.append({"title": title, "description": desc})

    return items


def collect_headlines() -> dict[str, list[dict]]:
    result = {}
    for category, urls in RSS_FEEDS.items():
        print(f"  Pobieram RSS: {category}...")
        items = []
        for url in urls:
            items.extend(fetch_rss(url))
        result[category] = items[:15]
    return result


# ── Streszczenie przez Groq ───────────────────────────────────────────────────

def summarize_with_groq(headlines: dict) -> str:
    today = date.today().strftime("%d %B %Y")

    labels = {
        "ai_robotyka": "AI / ROBOTYKA / AUTOMATYKA",
        "tech":        "TECH & NOWINKI",
        "kawa":        "KAWA",
        "polityka":    "POLITYKA",
        "trojmiasto":  "TRÓJMIASTO & GDAŃSK",
    }

    sections = []
    for cat, items in headlines.items():
        section = f"### {labels[cat]}\n"
        for item in items:
            section += f"- {item['title']}: {item['description']}\n"
        sections.append(section)

    raw_headlines = "\n".join(sections)

    prompt = f"""Dzisiaj jest {today}. Poniżej masz surowe nagłówki z serwisów informacyjnych z ostatnich 48 godzin.

{raw_headlines}

Przygotuj poranny digest dla studenta automatyki i robotyki z Gdańska, który interesuje się AI, systemami sterowania, kawą i lokalnym życiem Trójmiasta.

ZASADY FILTROWANIA — bądź surowy:
- Wybierz TYLKO rzeczy naprawdę przełomowe, zaskakujące lub bezpośrednio przydatne. Pomiń wszystko rutynowe.
- AI/robotyka: tylko prawdziwe przełomy, nowe modele, ciekawe zastosowania w automatyce/sterowaniu — nie każda aktualizacja produktu
- Tech: tylko coś co zmienia reguły gry lub jest naprawdę nowe
- Kawa: każda nowość jest ciekawa — nowe metody, przepisy, odkrycia dotyczące kawy
- Polityka: TYLKO jeśli coś kluczowego dla Polski lub Europy — jeśli nic takiego nie ma, pomiń tę sekcję całkowicie
- Trójmiasto: lokalne wydarzenia, ciekawostki z Gdańska, Gdyni, Sopotu, cokolwiek dot. Politechniki Gdańskiej

Jeśli w danej kategorii nie ma nic wartego uwagi — po prostu pomiń tę sekcję.

Formatuj DOKŁADNIE tak (bez żadnego dodatkowego tekstu przed ani po):

🤖 AI & ROBOTYKA
• [info]

💻 TECH
• [info]

☕ KAWA
• [info]

🏛️ POLITYKA
• [info]

🌊 TRÓJMIASTO
• [info]

Dobrego dnia, inżynierze!"""

    data = json.dumps({
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "Jesteś redaktorem który pisze zwięźle i konkretnie po polsku. Filtruj bezlitośnie — tylko rzeczy naprawdę warte uwagi. Wolisz napisać mniej niż wypełniać miejsce byle czym."
            },
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1024,
        "temperature": 0.3,
    }).encode("utf-8")

    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection("api.groq.com", context=ctx, timeout=30)
    conn.request(
        "POST",
        "/openai/v1/chat/completions",
        body=data,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "python-httpx/0.27.0",
            "Accept": "application/json",
        },
    )
    resp = conn.getresponse()
    body = resp.read()
    if resp.status != 200:
        print(f"  Groq error {resp.status}: {body[:500]}")
        raise Exception(f"Groq HTTP {resp.status}")
    result = json.loads(body)
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
