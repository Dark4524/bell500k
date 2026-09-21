import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "settings.json"
QUEUE_PATH = BASE_DIR / "queue.json"
JST = ZoneInfo("Asia/Tokyo")
TOKEN_URI = "https://oauth2.googleapis.com/token"


def load_json(path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_queue(items):
    with QUEUE_PATH.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
        f.write("\n")


def credentials_from_env(scope):
    required = [
        "YOUTUBE_CLIENT_ID",
        "YOUTUBE_REFRESH_TOKEN",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Missing GitHub Actions secrets: " + ", ".join(missing)
        )

    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri=TOKEN_URI,
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
        scopes=[scope],
    )
    creds.refresh(Request())
    return creds


def ffprobe_video(path):
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height:format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise RuntimeError("ffprobe is not installed on this runner.")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "ffprobe failed: " + (exc.stderr or "")[:300]
        )

    data = json.loads(result.stdout)
    streams = data.get("streams") or []
    if not streams:
        raise RuntimeError("No video stream found.")

    stream = streams[0]
    duration = float((data.get("format") or {}).get("duration") or 0)
    return {
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "duration": duration,
    }


def validate_item(item, settings):
    errors = []

    if not item.get("id"):
        errors.append("id is required")

    path = Path(str(item.get("file") or ""))
    if not path.is_absolute():
        path = (BASE_DIR.parent / path).resolve()

    if not path.exists():
        errors.append(f"video file not found: {path}")
        return errors, path, None

    allowed = {
        str(x).lower()
        for x in settings.get(
            "allowed_video_extensions", [".mp4", ".mov", ".m4v"]
        )
    }
    if path.suffix.lower() not in allowed:
        errors.append(f"video extension not allowed: {path.suffix}")

    title = str(item.get("title") or "").strip()
    if not title:
        errors.append("title is required")
    if len(title) > int(settings.get("title_max_characters", 100)):
        errors.append("title exceeds configured maximum")

    description = str(item.get("description") or "")
    if len(description) > int(
        settings.get("description_max_characters", 5000)
    ):
        errors.append("description exceeds configured maximum")

    info = None
    if not errors:
        info = ffprobe_video(path)
        if (
            settings.get("require_vertical_video", True)
            and info["height"] <= info["width"]
        ):
            errors.append(
                f"vertical video required: {info['width']}x{info['height']}"
            )

        max_duration = float(settings.get("max_duration_seconds", 180))
        if info["duration"] <= 0:
            errors.append("video duration could not be read")
        elif info["duration"] > max_duration:
            errors.append(
                f"duration {info['duration']:.1f}s exceeds {max_duration:.0f}s"
            )

    return errors, path, info


def uploaded_today(items, today):
    return sum(
        1
        for item in items
        if item.get("status") == "uploaded"
        and str(item.get("uploaded_at") or "").startswith(today)
    )


def upload_video(item, path, settings):
    scope = settings.get(
        "oauth_scope",
        "https://www.googleapis.com/auth/youtube.upload",
    )
    creds = credentials_from_env(scope)
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    privacy = str(
        item.get("privacy_status")
        or settings.get("default_privacy_status", "private")
    )
    if privacy != "private":
        raise RuntimeError(
            "Safety lock: automated YouTube upload is currently private-only."
        )

    body = {
        "snippet": {
            "title": item["title"],
            "description": item.get("description", ""),
            "categoryId": str(
                item.get("category_id")
                or settings.get("category_id", "28")
            ),
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(path),
        mimetype="video/*",
        resumable=True,
    )
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )
    response = request.execute()
    video_id = response.get("id")
    if not video_id:
        raise RuntimeError("YouTube upload succeeded but no video id returned.")
    return video_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["validate", "upload"],
        default="validate",
    )
    args = parser.parse_args()

    settings = load_json(SETTINGS_PATH, {})
    queue = load_json(QUEUE_PATH, [])
    if not isinstance(queue, list):
        raise RuntimeError("youtube_auto/queue.json must be a JSON array.")

    if args.mode == "upload" and not settings.get("enabled", False):
        print("YOUTUBE_UPLOAD_DISABLED")
        return

    now = datetime.now(JST)
    today = now.date().isoformat()
    max_daily = int(settings.get("max_uploads_per_day", 1))

    target = None
    for item in queue:
        if item.get("status") != "ready":
            continue
        scheduled_date = str(item.get("date") or "")
        if scheduled_date and scheduled_date > today:
            continue
        target = item
        break

    if target is None:
        print(f"NO_READY_YOUTUBE_VIDEO date={today}")
        return

    errors, path, info = validate_item(target, settings)
    if errors:
        target["status"] = "blocked"
        target["last_error"] = " | ".join(errors)[:1000]
        target["last_attempt_at"] = now.isoformat()
        save_queue(queue)
        raise RuntimeError(target["last_error"])

    print(
        "YOUTUBE_VALIDATE_OK "
        f"id={target.get('id')} "
        f"size={info['width']}x{info['height']} "
        f"duration={info['duration']:.1f}s "
        f"file={path.name}"
    )

    if args.mode == "validate":
        return

    if uploaded_today(queue, today) >= max_daily:
        print(f"YOUTUBE_DAILY_LIMIT_REACHED limit={max_daily}")
        return

    target["attempts"] = int(target.get("attempts", 0)) + 1
    target["last_attempt_at"] = now.isoformat()
    save_queue(queue)

    try:
        video_id = upload_video(target, path, settings)
    except Exception as exc:
        target["status"] = "error"
        target["last_error"] = str(exc)[:1000]
        save_queue(queue)
        raise

    target["status"] = "uploaded"
    target["youtube_video_id"] = video_id
    target["uploaded_at"] = now.isoformat()
    target["privacy_status"] = "private"
    target["last_error"] = None
    save_queue(queue)
    print(f"YOUTUBE_UPLOAD_OK id={target.get('id')} video_id={video_id}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
