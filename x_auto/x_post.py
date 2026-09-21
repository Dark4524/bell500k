import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from requests_oauthlib import OAuth1

API_URL = "https://api.x.com/2/tweets"
QUEUE_PATH = Path(__file__).with_name("queue.json")
JST = ZoneInfo("Asia/Tokyo")


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


def create_post(text):
    response = requests.post(
        API_URL,
        auth=auth(),
        json={"text": text},
        timeout=30,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"X create failed: HTTP {response.status_code}: {response.text[:500]}"
        )
    data = response.json().get("data", {})
    post_id = data.get("id")
    if not post_id:
        raise RuntimeError("X create succeeded but no post id was returned.")
    return post_id


def delete_post(post_id):
    response = requests.delete(
        f"{API_URL}/{post_id}",
        auth=auth(),
        timeout=30,
    )
    if response.status_code not in (200, 204):
        raise RuntimeError(
            f"X delete failed: HTTP {response.status_code}: {response.text[:500]}"
        )


def load_queue():
    if not QUEUE_PATH.exists():
        return []
    with QUEUE_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise RuntimeError("queue.json must contain a JSON array.")
    return data


def save_queue(items):
    with QUEUE_PATH.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
        f.write("\n")


def run_test():
    text = "X API自動投稿の接続テストです。設定確認後に自動削除します。"
    post_id = create_post(text)
    print(f"TEST_CREATE_OK post_id={post_id}")
    time.sleep(3)
    delete_post(post_id)
    print("TEST_DELETE_OK")


def run_scheduled(slot):
    now = datetime.now(JST)
    today = now.date().isoformat()
    items = load_queue()

    target = None
    for item in items:
        if item.get("status") != "ready":
            continue
        if item.get("slot") != slot:
            continue
        scheduled_date = item.get("date")
        if scheduled_date and scheduled_date > today:
            continue
        text = (item.get("text") or "").strip()
        if not text:
            continue
        target = item
        break

    if target is None:
        print(f"NO_READY_POST slot={slot} date={today}")
        return

    post_id = create_post(target["text"])
    target["status"] = "posted"
    target["tweet_id"] = post_id
    target["posted_at"] = now.isoformat()
    save_queue(items)
    print(f"POST_OK queue_id={target.get('id')} post_id={post_id} slot={slot}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["scheduled", "test"], required=True)
    parser.add_argument(
        "--slot",
        choices=["morning", "midday", "evening"],
        default="evening",
    )
    args = parser.parse_args()

    if args.mode == "test":
        run_test()
    else:
        run_scheduled(args.slot)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
