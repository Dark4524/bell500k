import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

import requests
from requests_oauthlib import OAuth1

API_URL = "https://api.x.com/2/tweets"
BASE_DIR = Path(__file__).resolve().parent
QUEUE_PATH = BASE_DIR / "queue.json"
SETTINGS_PATH = BASE_DIR / "settings.json"
JST = ZoneInfo("Asia/Tokyo")

DEFAULT_SETTINGS = {
    "enabled": True,
    "max_posts_per_day": 2,
    "max_attempts_per_item": 2,
    "block_exact_duplicates": True,
    "strip_hashtags": True,
    "max_raw_characters": 280,
    "metrics_enabled": False,
    "metrics_checkpoints_hours": [24, 72],
    "max_url_posts_per_7_days": 2,
    "allowed_link_domains": ["dark4524.github.io", "x.com"],
}


def load_settings():
    settings = DEFAULT_SETTINGS.copy()
    if SETTINGS_PATH.exists():
        with SETTINGS_PATH.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            settings.update(loaded)
    return settings


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


def sanitize_post_text(text, settings):
    # Convert accidental literal \n sequences from JSON editing into real line breaks.
    text = text.replace("\\n", "\n").strip()

    # We observed a 403 on a hashtagged live post while the same post succeeded
    # without hashtags. Until the account has more history, strip only hashtag
    # markers that start a whitespace-delimited token.
    if settings.get("strip_hashtags", True):
        text = re.sub(r"(?<!\S)#([^\s#]+)", r"\1", text)
    return text.strip()


def normalize_for_duplicate(text):
    return re.sub(r"\s+", " ", text.strip()).casefold()


def extract_urls(text):
    return re.findall(r"https?://[^\\s]+", text)


def validate_urls(text, settings):
    urls = extract_urls(text)
    allowed = {str(x).lower() for x in settings.get("allowed_link_domains", [])}
    for raw in urls:
        cleaned = raw.rstrip(".,、。)]}＞>」』")
        host = (urlparse(cleaned).hostname or "").lower()
        if not host:
            raise RuntimeError(f"INVALID_URL: {raw}")
        if allowed and host not in allowed:
            raise RuntimeError(f"UNAPPROVED_LINK_DOMAIN: {host}")
    return urls


def url_posts_in_last_7_days(items, now):
    threshold = now - timedelta(days=7)
    count = 0
    for item in items:
        if item.get("status") != "posted":
            continue
        posted_at = item.get("posted_at")
        try:
            dt = datetime.fromisoformat(str(posted_at))
        except (TypeError, ValueError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        if dt.astimezone(JST) < threshold:
            continue
        prior = item.get("posted_text") or item.get("text") or ""
        if extract_urls(prior):
            count += 1
    return count


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


def posted_today_count(items, today):
    return sum(
        1
        for item in items
        if item.get("status") == "posted"
        and str(item.get("posted_at", "")).startswith(today)
    )


def is_duplicate(candidate_text, items, target_id):
    candidate = normalize_for_duplicate(candidate_text)
    for item in items:
        if item.get("id") == target_id:
            continue
        if item.get("status") != "posted":
            continue
        prior = item.get("posted_text") or item.get("text") or ""
        if normalize_for_duplicate(prior) == candidate:
            return True
    return False


def run_test():
    text = "X API自動投稿の接続テストです。設定確認後に自動削除します。"
    post_id = create_post(text)
    print(f"TEST_CREATE_OK post_id={post_id}")
    time.sleep(3)
    delete_post(post_id)
    print("TEST_DELETE_OK")


def run_scheduled(slot):
    settings = load_settings()
    now = datetime.now(JST)
    today = now.date().isoformat()
    items = load_queue()

    if not settings.get("enabled", True):
        print("AUTO_POST_DISABLED")
        return

    daily_limit = int(settings.get("max_posts_per_day", 2))
    if posted_today_count(items, today) >= daily_limit:
        print(f"DAILY_LIMIT_REACHED limit={daily_limit} date={today}")
        return

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

    original_text = target["text"]
    post_text = sanitize_post_text(original_text, settings)

    if post_text != original_text:
        print("POST_TEXT_SANITIZED")
        target["posted_text"] = post_text

    try:
        urls = validate_urls(post_text, settings)
    except Exception as exc:
        target["status"] = "blocked"
        target["last_error"] = str(exc)[:500]
        target["last_attempt_at"] = now.isoformat()
        save_queue(items)
        raise

    if urls:
        max_url_posts = int(settings.get("max_url_posts_per_7_days", 2))
        recent_url_posts = url_posts_in_last_7_days(items, now)
        if recent_url_posts >= max_url_posts:
            target["status"] = "blocked"
            target["last_error"] = (
                f"URL_POST_LIMIT_REACHED count={recent_url_posts} "
                f"limit={max_url_posts} window=7d"
            )
            target["last_attempt_at"] = now.isoformat()
            save_queue(items)
            raise RuntimeError(target["last_error"])

    max_chars = int(settings.get("max_raw_characters", 280))
    if len(post_text) > max_chars:
        target["status"] = "blocked"
        target["last_error"] = (
            f"TEXT_TOO_LONG raw_characters={len(post_text)} limit={max_chars}"
        )
        target["last_attempt_at"] = now.isoformat()
        save_queue(items)
        raise RuntimeError(target["last_error"])

    if settings.get("block_exact_duplicates", True) and not target.get(
        "allow_duplicate", False
    ):
        if is_duplicate(post_text, items, target.get("id")):
            target["status"] = "blocked"
            target["last_error"] = "DUPLICATE_POST_BLOCKED"
            target["last_attempt_at"] = now.isoformat()
            save_queue(items)
            raise RuntimeError(target["last_error"])

    target["attempts"] = int(target.get("attempts", 0)) + 1
    target["last_attempt_at"] = now.isoformat()
    save_queue(items)

    try:
        post_id = create_post(post_text)
    except Exception as exc:
        target["last_error"] = str(exc)[:500]
        max_attempts = int(settings.get("max_attempts_per_item", 2))
        if target["attempts"] >= max_attempts:
            target["status"] = "error"
        else:
            target["status"] = "ready"
        save_queue(items)
        raise

    target["status"] = "posted"
    target["tweet_id"] = post_id
    target["posted_at"] = now.isoformat()
    target["last_error"] = None
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
