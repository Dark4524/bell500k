import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from requests_oauthlib import OAuth1

BASE_DIR = Path(__file__).resolve().parent
QUEUE_PATH = BASE_DIR / "queue.json"
SETTINGS_PATH = BASE_DIR / "settings.json"
API_URL = "https://api.x.com/2/tweets"
JST = ZoneInfo("Asia/Tokyo")


def load_json(path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_queue(items):
    with QUEUE_PATH.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
        f.write("\n")


def auth():
    required = [
        "X_API_KEY",
        "X_API_KEY_SECRET",
        "X_ACCESS_TOKEN",
        "X_ACCESS_TOKEN_SECRET",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing GitHub Actions secrets: " + ", ".join(missing))
    return OAuth1(
        os.environ["X_API_KEY"],
        os.environ["X_API_KEY_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def fetch_public_metrics(post_id):
    response = requests.get(
        f"{API_URL}/{post_id}",
        auth=auth(),
        params={"tweet.fields": "public_metrics"},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"X metrics failed: HTTP {response.status_code}: {response.text[:500]}"
        )
    data = response.json().get("data", {})
    metrics = data.get("public_metrics")
    if not isinstance(metrics, dict):
        raise RuntimeError("X metrics response did not include public_metrics.")
    return metrics


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def main():
    settings = load_json(SETTINGS_PATH, {})
    if not settings.get("metrics_enabled", False):
        print("METRICS_DISABLED")
        return

    checkpoints = sorted(
        int(x) for x in settings.get("metrics_checkpoints_hours", [24, 72])
    )
    items = load_json(QUEUE_PATH, [])
    now = datetime.now(JST)
    changed = False
    api_reads = 0

    for item in items:
        if item.get("status") != "posted" or not item.get("tweet_id"):
            continue

        posted_at = parse_iso(item.get("posted_at"))
        if posted_at is None:
            continue
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=JST)

        age_hours = (now - posted_at.astimezone(JST)).total_seconds() / 3600
        snapshots = item.setdefault("metrics_snapshots", [])

        completed = {
            int(s.get("checkpoint_target_hours"))
            for s in snapshots
            if s.get("checkpoint_target_hours") is not None
        }
        due = next(
            (
                cp
                for cp in checkpoints
                if age_hours >= cp and cp not in completed
            ),
            None,
        )
        if due is None:
            continue

        try:
            metrics = fetch_public_metrics(item["tweet_id"])
            api_reads += 1
            snapshots.append(
                {
                    "checkpoint_target_hours": due,
                    "observed_at": now.isoformat(),
                    "actual_age_hours": round(age_hours, 1),
                    "public_metrics": metrics,
                }
            )
            item["metrics_last_error"] = None
            changed = True
            print(
                f"METRICS_OK queue_id={item.get('id')} "
                f"checkpoint={due}h age={age_hours:.1f}h"
            )
        except Exception as exc:
            item["metrics_last_error"] = str(exc)[:500]
            item["metrics_last_attempt_at"] = now.isoformat()
            changed = True
            print(
                f"METRICS_ERROR queue_id={item.get('id')} error={exc}",
                flush=True,
            )

    if changed:
        save_queue(items)

    print(f"METRICS_DONE api_reads={api_reads}")


if __name__ == "__main__":
    main()
