import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent
QUEUE_PATH = BASE_DIR / "queue.json"
REPORT_PATH = BASE_DIR / "report.json"
JST = ZoneInfo("Asia/Tokyo")


def load_queue():
    if not QUEUE_PATH.exists():
        return []
    with QUEUE_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def main():
    items = load_queue()
    now = datetime.now(JST)
    status_counts = Counter(str(x.get("status") or "unknown") for x in items)

    posted = [x for x in items if x.get("status") == "posted"]
    latest = None
    if posted:
        latest = max(
            posted,
            key=lambda x: str(x.get("posted_at") or ""),
        )

    metrics_snapshots = sum(
        len(x.get("metrics_snapshots") or [])
        for x in posted
        if isinstance(x.get("metrics_snapshots") or [], list)
    )
    posts_with_metrics = sum(
        1
        for x in posted
        if isinstance(x.get("metrics_snapshots"), list)
        and len(x.get("metrics_snapshots")) > 0
    )

    report = {
        "generated_at": now.isoformat(),
        "queue_items": len(items),
        "status_counts": dict(sorted(status_counts.items())),
        "posted_count": len(posted),
        "posts_with_metrics": posts_with_metrics,
        "metrics_snapshot_count": metrics_snapshots,
        "latest_post": None,
    }

    if latest:
        report["latest_post"] = {
            "queue_id": latest.get("id"),
            "tweet_id": latest.get("tweet_id"),
            "posted_at": latest.get("posted_at"),
            "slot": latest.get("slot"),
        }

    with REPORT_PATH.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(
        "REPORT_OK "
        f"items={report['queue_items']} "
        f"posted={report['posted_count']} "
        f"metric_snapshots={report['metrics_snapshot_count']}"
    )


if __name__ == "__main__":
    main()
