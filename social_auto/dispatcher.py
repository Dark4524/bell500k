import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "platforms.json"
QUEUE_PATH = BASE_DIR / "queue.json"
VALID_PLATFORMS = {"x", "youtube", "instagram", "tiktok"}


def load(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_item(item):
    errors = []
    if not item.get("id"):
        errors.append("id is required")
    platforms = item.get("platforms") or []
    if not isinstance(platforms, list) or not platforms:
        errors.append("platforms must be a non-empty list")
    else:
        unknown = sorted(set(platforms) - VALID_PLATFORMS)
        if unknown:
            errors.append("unknown platforms: " + ", ".join(unknown))
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["dry-run"], default="dry-run")
    args = parser.parse_args()

    config = load(CONFIG_PATH)
    queue = load(QUEUE_PATH)

    if config.get("mode") != "dry-run" or args.mode != "dry-run":
        raise RuntimeError("Live multi-platform dispatch is not enabled.")

    if not isinstance(queue, list):
        raise RuntimeError("social_auto/queue.json must be a JSON array.")

    errors = []
    ready = 0
    for idx, item in enumerate(queue):
        item_errors = validate_item(item)
        if item_errors:
            errors.extend([f"item[{idx}]: {x}" for x in item_errors])
            continue
        if item.get("status") == "ready":
            ready += 1
            for platform in item.get("platforms", []):
                enabled = bool(
                    config.get("platforms", {})
                    .get(platform, {})
                    .get("enabled", False)
                )
                print(
                    f"DRY_RUN id={item.get('id')} platform={platform} "
                    f"platform_enabled={enabled}"
                )

    for err in errors:
        print("ERROR:", err, file=sys.stderr)

    print(
        f"SOCIAL_DRY_RUN items={len(queue)} ready={ready} errors={len(errors)}"
    )
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
