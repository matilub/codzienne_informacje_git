name: Poranny digest

on:
  schedule:
    - cron: "0 6 * * *"   # 6:00 UTC = 7:00 lub 8:00 czasu polskiego
  workflow_dispatch:        # pozwala uruchomić ręcznie z panelu GitHub

jobs:
  send-digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Skonfiguruj Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Zainstaluj zależności
        run: pip install anthropic

      - name: Uruchom agenta
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          NTFY_TOPIC:        ${{ secrets."codzienne_informacje" }}
        run: python agent.py