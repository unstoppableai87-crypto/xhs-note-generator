"""Google Sheets + Drive backed storage for the shared note queue.

This lets customer submissions (from customer_form.py, typically deployed
as its own Streamlit Cloud app) and creator approvals (from app.py) land in
the same durable queue, instead of each process's own local disk - which is
what makes the "send a link to a guest" flow actually work across machines.

Sheet layout (single worksheet named "Queue"):
  id | created_at | status | title | content | hashtags | image_urls | source
"""
import io
import time

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

import config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_HEADERS = ["id", "created_at", "status", "title", "content", "hashtags", "image_urls", "source"]

PENDING = "待发布 Pending"
NEEDS_REVIEW = "需要人工复核 Needs Review"
POSTED = "已发布 Posted"


class StorageError(RuntimeError):
    pass


def _get_credentials():
    raw = config.get_setting("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        import json

        info = json.loads(raw)
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    path = config.get_setting("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    try:
        return Credentials.from_service_account_file(path, scopes=SCOPES)
    except FileNotFoundError as e:
        raise StorageError(
            f"找不到 Google service account 凭证（{path}）。"
            " 请按 SETUP_CLOUD.md 的步骤创建并放置 service_account.json，"
            " 或在 .env / Streamlit secrets 中设置 GOOGLE_SERVICE_ACCOUNT_JSON。"
        ) from e


def _get_clients():
    creds = _get_credentials()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)
    return gc, drive


def _get_sheet(gc):
    sheet_id = config.get_setting("GOOGLE_SHEET_ID")
    if not sheet_id:
        raise StorageError("GOOGLE_SHEET_ID 未设置，请在 .env / Streamlit secrets 中配置。")
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet("Queue")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Queue", rows=1000, cols=len(SHEET_HEADERS))
        ws.append_row(SHEET_HEADERS)
    return ws


def _upload_image(drive, filename, data):
    folder_id = config.get_setting("GOOGLE_DRIVE_FOLDER_ID")
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype="image/jpeg", resumable=False)
    metadata = {"name": filename}
    if folder_id:
        metadata["parents"] = [folder_id]
    file = drive.files().create(body=metadata, media_body=media, fields="id").execute()
    file_id = file["id"]
    drive.permissions().create(fileId=file_id, body={"role": "reader", "type": "anyone"}).execute()
    return f"https://drive.google.com/uc?export=view&id={file_id}"


def save_draft(title, content, hashtags, image_files, source="creator", status=PENDING):
    """image_files: list of (filename, bytes) tuples. Returns the new draft id."""
    gc, drive = _get_clients()
    ws = _get_sheet(gc)

    image_urls = [_upload_image(drive, filename, data) for filename, data in (image_files or [])]

    draft_id = time.strftime("%Y%m%d_%H%M%S")
    ws.append_row([
        draft_id,
        draft_id,
        status,
        title,
        content,
        ", ".join(hashtags),
        ", ".join(image_urls),
        source,
    ])
    return draft_id


def list_drafts():
    gc, _ = _get_clients()
    ws = _get_sheet(gc)
    records = ws.get_all_records()

    drafts = []
    for i, r in enumerate(records):
        drafts.append({
            "row_index": i + 2,  # header is row 1, data starts at row 2
            "id": r.get("id"),
            "created_at": r.get("created_at"),
            "status": r.get("status"),
            "title": r.get("title"),
            "content": r.get("content"),
            "hashtags": [h.strip() for h in (r.get("hashtags") or "").split(",") if h.strip()],
            "image_urls": [u.strip() for u in (r.get("image_urls") or "").split(",") if u.strip()],
            "source": r.get("source"),
        })
    drafts.reverse()
    return drafts


def update_status(row_index, status):
    gc, _ = _get_clients()
    ws = _get_sheet(gc)
    headers = ws.row_values(1)
    col = headers.index("status") + 1
    ws.update_cell(row_index, col, status)


def delete_draft(row_index):
    gc, _ = _get_clients()
    ws = _get_sheet(gc)
    ws.delete_rows(row_index)


def copy_text(draft):
    return draft["title"] + "\n\n" + draft["content"] + "\n\n" + " ".join(f"#{h}" for h in draft["hashtags"])
