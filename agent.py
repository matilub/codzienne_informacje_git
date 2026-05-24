"""
Codzienny digest newsów — Claude API + ntfy.sh
Tematy: Technologia i AI, Nauka i zdrowie, Kultura i rozrywka
Wysyłka: push na telefon przez ntfy.sh (darmowe, bez rejestracji)
"""

import anthropic
import urllib.request
import urllib.error
import json
import os
from datetime import date

# ── Konfiguracja ──────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "sk-ant-...")
NTFY_TOPIC        = os.environ.get("NTFY_TOPIC", "codzienne_informacje")  # zmień na swój unikalny temat
NTFY_SERVER       = "https://ntfy.sh"

TOPICS = [
    "technologia i sztuczna inteligencja (nowe modele AI, przełomowe badania, ciekawe produkty tech)",
    "nauka i zdrowie (odkrycia naukowe, medycyna, psychologia, zdrowy styl życia)",
    "kultura i rozrywka (filmy, muzyka, książki, ciekawe zjawiska kulturowe)",
]

# ── Pobieranie newsów przez Claude ────────────────────────────────────────────

def fetch_digest() -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    today = date.today().strftime("%d %B %Y")
    topics_str = "\n".join(f"- {t}" for t in TOPICS)

    prompt = f"""Dzisiaj jest {today}. Przygotuj krótki poranny digest newsów na podstawie aktualnych informacji z internetu.

Interesują mnie następujące obszary:
{topics_str}

Dla każdego obszaru wybierz 2-3 najciekawsze informacje z ostatnich 24-48 godzin.
Każdy punkt napisz w 1-2 zdaniach po polsku — zwięźle i konkretnie.
Nie używaj markdown, gwiazdek ani emoji (poza jedną ikoną na początku sekcji).
Formatuj tak:

📱 TECH & AI
• [info 1]
• [info 2]

🔬 NAUKA & ZDROWIE
• [info 1]
• [info 2]

🎬 KULTURA & ROZRYWKA
• [info 1]
• [info 2]

Na końcu dodaj jedno zdanie "Dobrego dnia!" jako zamknięcie."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    text_blocks = [b.text for b in response.content if hasattr(b, "text") and b.text]
    return "\n".join(text_blocks).strip()


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
        f"{NTFY_SERVER}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        status = resp.status
        print(f"ntfy.sh → HTTP {status}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Pobieram digest...")
    digest = fetch_digest()
    print("─" * 50)
    print(digest)
    print("─" * 50)

    print("Wysyłam powiadomienie...")
    send_notification(digest)
    print("Gotowe! ✓")


if __name__ == "__main__":
    main()
