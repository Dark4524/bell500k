import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
QUEUE_PATH = BASE_DIR / "queue.json"
SETTINGS_PATH = BASE_DIR / "settings.json"
VALID_SLOTS = {"morning", "midday", "evening"}
VALID_STATUS = {"ready", "posted", "blocked", "error", "hold"}


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize(text):
    return re.sub(r"\s+", " ", str(text or "").strip()).casefold()


def main():
    errors = []
    warnings = []

    queue = load_json(QUEUE_PATH)
    settings = load_json(SETTINGS_PATH)

    if not isinstance(queue, list):
        errors.append("queue.json must be a JSON array")
        queue = []

    ids = []
    ready_per_date = Counter()
    seen_texts = {}

    for idx, item in enumerate(queue):
        label = f"item[{idx}]"
        if not isinstance(item, dict):
            errors.append(f"{label}: must be an object")
            continue

        item_id = str(item.get("id") or "").strip()
        if not item_id:
            errors.append(f"{label}: id is required")
        else:
            ids.append(item_id)
            label = item_id

        status = item.get("status")
        if status not in VALID_STATUS:
            errors.append(f"{label}: invalid status={status!r}")

        slot = item.get("slot")
        if slot not in VALID_SLOTS:
            errors.append(f"{label}: invalid slot={slot!r}")

        d = item.get("date")
        if d:
            try:
                date.fromisoformat(str(d))
            except ValueError:
                errors.append(f"{label}: invalid date={d!r}")

        text = str(item.get("text") or "").replace("\\n", "\n").strip()
        if status == "ready" and not text:
            errors.append(f"{label}: ready item requires text")

        max_chars = int(settings.get("max_raw_characters", 280))
        if len(text) > max_chars:
            errors.append(
                f"{label}: raw text length {len(text)} exceeds configured {max_chars}"
            )

        if status == "ready" and d:
            ready_per_date[str(d)] += 1

        norm = normalize(text)
        if norm:
            if norm in seen_texts and not item.get("allow_duplicate", False):
                warnings.append(
                    f"{label}: same text as {seen_texts[norm]} (runtime will block duplicate)"
                )
            else:
                seen_texts[norm] = label

    duplicate_ids = [k for k, v in Counter(ids).items() if v > 1]
    for item_id in duplicate_ids:
        errors.append(f"duplicate id: {item_id}")

    daily_limit = int(settings.get("max_posts_per_day", 2))
    for d, count in ready_per_date.items():
        if count > daily_limit:
            warnings.append(
                f"{d}: {count} ready posts exceed daily runtime limit {daily_limit}"
            )

    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)

    print(
        f"QUEUE_CHECK items={len(queue)} errors={len(errors)} warnings={len(warnings)}"
    )
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
