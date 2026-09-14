import json
import os
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build as gbuild
from googleapiclient.http import MediaFileUpload
from .config import ROOT, CONFIG

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
CLIENT_SECRET = ROOT / "client_secret.json"
TOKEN = ROOT / "token.json"
YOUTUBE_SCOPES = SCOPES


def _service_from_refresh_token():
    """CI (tarayıcısız) akışı: YOUTUBE_REFRESH_TOKEN + CLIENT_SECRETS_JSON/client_secret.json."""
    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")
    if not refresh_token:
        return None
    client_secrets_json = os.getenv("CLIENT_SECRETS_JSON")
    if client_secrets_json:
        config = json.loads(client_secrets_json)
    elif CLIENT_SECRET.exists():
        config = json.loads(CLIENT_SECRET.read_text(encoding="utf-8"))
    else:
        raise RuntimeError("CLIENT_SECRETS_JSON bulunamadı!")
    client_config = config.get("installed") or config.get("web") or next(iter(config.values()))
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_config["client_id"],
        client_secret=client_config["client_secret"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return gbuild("youtube", "v3", credentials=creds)


def get_service():
    svc = _service_from_refresh_token()
    if svc is not None:
        return svc
    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return gbuild("youtube", "v3", credentials=creds)


def upload_video(video_path: Path, title: str, description: str, tags: list[str],
                 publish_at: str | None = None) -> str:
    yt = get_service()
    up = CONFIG["upload"]
    all_tags = list({*tags, *up["default_tags"]})

    status = {"selfDeclaredMadeForKids": up["made_for_kids"]}
    if publish_at:
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at
    else:
        status["privacyStatus"] = up["privacy"]
    if "#shorts" not in title.lower():
        title = f"{title} #shorts"

    body = {
        "snippet": {
            "title": title[:95],
            "description": description,
            "tags": all_tags,
            "categoryId": up["category_id"],
        },
        "status": status,
    }
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]
