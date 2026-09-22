"""Refresh data/rates.json's live exchange rates and regenerate the app's
data file — the backing script for the update-rates skill.

Run from the project root: python3 scripts/update_rates.py

What it does:
1. Fetches live USD-based rates from open.er-api.com (free, no API key)
   and derives EUR/CHF/CZK/JPY -> COP from them.
2. Writes each currency's new *base* rate into data/rates.json — the app's
   displayed rate, and every price conversion, is `baseRate * markup` at
   generate time (scripts/generate_data.py's `rate_for`), so nothing else
   needs to change: no cached totals to re-price, no formulas to touch.
   `markup` (1.05, the user's standing "always add 5% more" policy) is
   read from the same file and left untouched — edit it by hand in
   data/rates.json if that policy ever changes.
3. Updates `updatedAt` to today's date.
4. Regenerates src/data/generated/itinerary.generated.ts.

This used to also patch Excel formula cells and re-price every line item's
cached total across every sheet, plus (for JPY specifically) regex-patch a
Python source constant — all of that inference is gone now that every
price is computed fresh from data/*.json at generate time.
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RATES_PATH = ROOT / "data" / "rates.json"


def fetch_live_rates() -> dict[str, float]:
    """USD-based rates from a free, keyless API; derive EUR/CHF/CZK/USD/JPY -> COP."""
    with urllib.request.urlopen("https://open.er-api.com/v6/latest/USD", timeout=15) as resp:
        data = json.load(resp)
    if data.get("result") != "success":
        raise RuntimeError(f"rate API did not return success: {data}")
    r = data["rates"]
    usd_to_cop = r["COP"]
    return {
        "EUR": usd_to_cop / r["EUR"],
        "CHF": usd_to_cop / r["CHF"],
        "CZK": usd_to_cop / r["CZK"],
        "USD": usd_to_cop,
        "JPY": usd_to_cop / r["JPY"],
    }


def main():
    rates_doc = json.loads(RATES_PATH.read_text(encoding="utf-8"))
    live = fetch_live_rates()

    print("Live base rates fetched:")
    for code, value in live.items():
        # Round like the existing base rates (near-whole numbers; CZK and JPY
        # are small enough that a whole-number round would lose too much precision).
        rounded = round(value, 1) if code in ("CZK", "JPY") else round(value)
        old = rates_doc["rates"][code]["baseRate"]
        rates_doc["rates"][code]["baseRate"] = rounded
        print(f"  {code}: {old} -> {rounded} (rate shown in app, with {rates_doc['markup']}x markup: {round(rounded * rates_doc['markup'], 2)})")

    rates_doc["updatedAt"] = date.today().strftime("%d/%m/%Y")
    RATES_PATH.write_text(json.dumps(rates_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {RATES_PATH.relative_to(ROOT)}, updatedAt = {rates_doc['updatedAt']}")

    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_data.py")], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
