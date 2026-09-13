"""Add, update, or delete a single line item in a trip option's JSON file.

Run from the project root:
    python3 scripts/manage_item.py add --option alpes-suizos --category "Tours y Excursiones" \\
        --date "14 May 2027" --place "Zadar" --title "Tour a pie por el casco antiguo" \\
        --currency EUR --unit-amount 15 --quantity 3 \\
        --note "Tour guiado 2h, incluye entrada a la catedral" --link "https://example.com/tour"

    python3 scripts/manage_item.py update --option alpes-suizos --match-title "SIM card" \\
        --currency USD --unit-amount 45 --quantity 1 --note "..." --link "..."

    python3 scripts/manage_item.py delete --option alpes-suizos --match-title "Free tour"

This is the supported way to edit a line item — it's the same JSON file you
could open and edit by hand (data/options/<option>.json), just with the
same "don't guess on an ambiguous match" safety net a hand edit doesn't
give you for free, plus a word-count check on notes. It always regenerates
src/data/generated/itinerary.generated.ts afterward, so the app and the
data file never drift apart. Never hand-edit the generated .ts file.

`--option` is the file id (the JSON filename without ".json"), NOT the
option's display name shown in the app — see data/options/*.json's own
"name" field for that. This is deliberate: renaming an option (editing its
"name" field) never requires touching this script or its callers, since the
filename is a stable id independent of what's displayed.

`add` places the new item on the day matching `--date` (by day number +
month, e.g. "14 May 2027" -> the day already keyed "14 MAY"). If no such
day exists yet, add the day itself directly in the JSON file first (a day
needs a city/title/weather, which isn't line-item data) — this script only
ever adds items to a day that's already there. A dateless item (e.g.
"Durante el viaje", for a SIM card or travel insurance) lands on the
option's first day, matching where every existing trip-wide item already
sits.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPTIONS_DIR = ROOT / "data" / "options"

# The 3 options priced day-by-day (a workbook row per line item, in spirit).
# Orlando and Japón are shaped too differently for this generic tool — see
# CLAUDE.md's "Data" section for why, and edit their JSON files by hand.
OPTION_IDS = ["europa", "alpes-suizos", "crucero-en-pareja"]

CATEGORIES = {
    "Vuelos y Trenes", "Traslados", "Alojamiento", "Crucero",
    "Tours y Excursiones", "Comidas", "Seguro de Viaje", "Otros y Extras",
}
CURRENCIES = {"EUR", "CHF", "CZK", "USD", "COP"}

MONTHS_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def day_key(raw_date: str) -> str | None:
    match = re.search(r"(\d{1,2})\s*[–\-]?\s*(?:\d{1,2}\s*)?(Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic)", raw_date, re.IGNORECASE)
    if not match:
        return None
    return f"{int(match.group(1)):02d} {match.group(2).upper()}"


def word_count(text: str) -> int:
    return len(text.split())


def load_option(option_id: str) -> dict:
    path = OPTIONS_DIR / f"{option_id}.json"
    if not path.exists():
        raise SystemExit(f"No such option file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_option(option_id: str, doc: dict) -> None:
    path = OPTIONS_DIR / f"{option_id}.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_item(doc: dict, match_title: str, match_date: str | None = None) -> tuple[int, int]:
    """Same ambiguity-safety rules as the old Excel-cell version: (1) a
    case-sensitive exact title match wins outright; (2) failing that, a
    case-insensitive exact match, only if exactly one item qualifies; (3)
    otherwise a substring match, again only if exactly one qualifies. Any
    ambiguity at (2) or (3) raises instead of guessing.

    If `match_date` is given, candidates are filtered to items whose own
    `date` field exactly matches it first — needed for a title that's
    intentionally repeated once per day (e.g. "Comida del día")."""
    needle = match_title.strip()
    needle_lower = needle.lower()
    exact_ci: list[tuple[int, int, str]] = []
    substring: list[tuple[int, int, str]] = []
    case_sensitive_hit: tuple[int, int] | None = None
    for day_idx, day in enumerate(doc["days"]):
        for item_idx, item in enumerate(day["items"]):
            if match_date is not None and item.get("date", "") != match_date:
                continue
            title = item["title"]
            if title == needle:
                case_sensitive_hit = (day_idx, item_idx)
            if title.lower() == needle_lower:
                exact_ci.append((day_idx, item_idx, title))
            elif needle_lower in title.lower():
                substring.append((day_idx, item_idx, title))
    if case_sensitive_hit is not None:
        return case_sensitive_hit
    if len(exact_ci) > 1:
        listing = "; ".join(f"day {doc['days'][d]['dayKey']}: {t!r}" for d, _, t in exact_ci)
        raise SystemExit(f"--match-title {match_title!r} matches {len(exact_ci)} items that differ only by case, ambiguous: {listing}. Use --match-title with the exact case shown, or add --match-date.")
    if exact_ci:
        d, i, _ = exact_ci[0]
        return d, i
    if len(substring) > 1:
        listing = "; ".join(f"day {doc['days'][d]['dayKey']}: {t!r}" for d, _, t in substring)
        raise SystemExit(f"--match-title {match_title!r} matches {len(substring)} items, ambiguous: {listing}. Use a more specific --match-title, or add --match-date.")
    if substring:
        d, i, _ = substring[0]
        return d, i
    raise SystemExit(f"No item found in {doc['name']!r} matching title {match_title!r}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["add", "update", "delete"])
    parser.add_argument("--option", required=True, choices=OPTION_IDS)
    parser.add_argument("--category", choices=sorted(CATEGORIES))
    parser.add_argument("--place", default=None)
    parser.add_argument("--date", dest="date_text", help='e.g. "14 May 2027", or a dateless label like "Durante el viaje"')
    parser.add_argument("--title", help="Required for 'add'; optional for 'update' (keeps the matched title if omitted)")
    parser.add_argument("--match-title", help="Substring to find the item to update/delete")
    parser.add_argument("--match-date", help="Also filter --match-title candidates by exact item date text, for a title repeated once per day (e.g. \"Comida del día\")")
    parser.add_argument("--currency", choices=sorted(CURRENCIES))
    parser.add_argument("--unit-amount", type=float)
    parser.add_argument("--quantity", type=float)
    parser.add_argument("--note", help="Max 20 words — the single most relevant fact about this item")
    parser.add_argument("--link", default=None, help="Optional booking/info URL. Pass \"\" to remove an existing link.")
    args = parser.parse_args()

    if args.note is not None and word_count(args.note) > 20:
        raise SystemExit(f"Note is {word_count(args.note)} words (max 20): {args.note!r}")

    doc = load_option(args.option)

    if args.action == "delete":
        if not args.match_title:
            raise SystemExit("delete requires --match-title")
        day_idx, item_idx = find_item(doc, args.match_title, args.match_date)
        deleted = doc["days"][day_idx]["items"].pop(item_idx)
        save_option(args.option, doc)
        print(f"Deleted item from {doc['name']!r}, day {doc['days'][day_idx]['dayKey']}: {deleted['title']!r}")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_data.py")], check=True, cwd=ROOT)
        return

    if args.action == "add":
        missing = [f for f in ("category", "title", "currency", "unit_amount", "quantity", "date_text", "note") if getattr(args, f) is None]
        if missing:
            raise SystemExit(f"add requires: {', '.join(missing)}")
        if args.category not in CATEGORIES:
            raise SystemExit(f"Unknown category {args.category!r}. Must be one of: {sorted(CATEGORIES)}")
        key = day_key(args.date_text)
        if key is None:
            day_idx = 0  # dateless item (SIM card, insurance...) -> first day, matching every existing one
        else:
            day_idx = next((i for i, d in enumerate(doc["days"]) if d["dayKey"] == key), None)
            if day_idx is None:
                raise SystemExit(
                    f"No day {key!r} in {doc['name']!r} yet — add the day itself directly in "
                    f"data/options/{args.option}.json first (needs a city/title/weather), then re-run this."
                )
        item = {
            "category": args.category, "title": args.title, "currency": args.currency,
            "unitAmount": args.unit_amount, "quantity": args.quantity,
            "note": args.note, "place": args.place or "", "date": args.date_text, "link": args.link,
        }
        doc["days"][day_idx]["items"].append(item)
        save_option(args.option, doc)
        print(f"Added item to {doc['name']!r}, day {doc['days'][day_idx]['dayKey']}:")
        print(f"  {item['title']}  ·  {item['category']}")
        print(f"  {item['currency']} {item['unitAmount']} x {item['quantity']}")
        print(f"  Note: {item['note']}" + (f" | Link: {item['link']}" if item["link"] else ""))
        subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_data.py")], check=True, cwd=ROOT)
        return

    # update
    if not args.match_title:
        raise SystemExit("update requires --match-title")
    day_idx, item_idx = find_item(doc, args.match_title, args.match_date)
    item = doc["days"][day_idx]["items"][item_idx]
    if args.category is not None:
        if args.category not in CATEGORIES:
            raise SystemExit(f"Unknown category {args.category!r}. Must be one of: {sorted(CATEGORIES)}")
        item["category"] = args.category
    if args.place is not None:
        item["place"] = args.place
    if args.date_text is not None:
        item["date"] = args.date_text
    if args.title is not None:
        item["title"] = args.title
    if args.currency is not None:
        item["currency"] = args.currency
    if args.unit_amount is not None:
        item["unitAmount"] = args.unit_amount
    if args.quantity is not None:
        item["quantity"] = args.quantity
    if args.note is not None:
        item["note"] = args.note
    if args.link is not None:
        item["link"] = args.link or None
    save_option(args.option, doc)
    print(f"Updated item in {doc['name']!r}, day {doc['days'][day_idx]['dayKey']}:")
    print(f"  {item['title']}  ·  {item['category']}")
    print(f"  {item['currency']} {item['unitAmount']} x {item['quantity']}")
    print(f"  Note: {item['note']}" + (f" | Link: {item['link']}" if item["link"] else ""))
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_data.py")], check=True, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
