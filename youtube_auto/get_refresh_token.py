import argparse
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPE = "https://www.googleapis.com/auth/youtube.upload"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client-secrets",
        required=True,
        help="Path to OAuth client JSON downloaded from Google Cloud Console.",
    )
    args = parser.parse_args()

    path = Path(args.client_secrets)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(path),
        scopes=[SCOPE],
    )
    credentials = flow.run_local_server(
        host="localhost",
        port=0,
        authorization_prompt_message=(
            "Browser authorization is required once. "
            "Do not paste the returned token into chat."
        ),
        success_message=(
            "YouTube authorization completed. "
            "You can close this browser tab."
        ),
        open_browser=True,
        access_type="offline",
        prompt="consent",
    )

    if not credentials.refresh_token:
        raise SystemExit(
            "No refresh token returned. Revoke prior consent and authorize again."
        )

    result = {
        "client_id": credentials.client_id,
        "refresh_token": credentials.refresh_token,
        "scope": SCOPE,
    }
    if credentials.client_secret:
        result["client_secret"] = credentials.client_secret
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(
        "\nStore these values only in GitHub Actions Secrets. "
        "Do not commit them and do not paste them into ChatGPT."
    )


if __name__ == "__main__":
    main()
