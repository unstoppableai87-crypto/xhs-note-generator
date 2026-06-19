"""Supabase-backed storage for the shared note queue (Postgres table "queue"
+ a Storage bucket for photos).

This is what lets customer submissions (from customer_form.py, typically
deployed as its own Streamlit Cloud app) and creator approvals (from
app.py) land in the same durable queue, instead of each process's own
local disk. Chosen over Google Sheets/Drive because Supabase's free tier
needs no credit card to sign up.
"""
import time

from supabase import create_client

import config

PENDING = "待发布 Pending"
NEEDS_REVIEW = "需要人工复核 Needs Review"
POSTED = "已发布 Posted"

TABLE = "queue"


class StorageError(RuntimeError):
    pass


def _get_client():
    url = config.get_setting("SUPABASE_URL")
    key = config.get_setting("SUPABASE_KEY")
    if not url or not key:
        raise StorageError(
            "SUPABASE_URL / SUPABASE_KEY 未设置。请按 SETUP_CLOUD.md 的步骤创建 Supabase 项目，"
            "并在 .env / Streamlit secrets 中配置。"
        )
    return create_client(url, key)


def _upload_image(client, filename, data):
    bucket = config.get_setting("SUPABASE_BUCKET", "photos")
    path = f"{time.strftime('%Y%m%d_%H%M%S')}_{filename}"
    try:
        client.storage.from_(bucket).upload(path, data, {"content-type": "image/jpeg"})
    except Exception as e:
        raise StorageError(f"图片上传失败: {e}") from e
    return client.storage.from_(bucket).get_public_url(path)


def _new_id():
    return time.strftime("%Y%m%d_%H%M%S_") + f"{int(time.time() * 1000) % 1000:03d}"


def save_draft(title, content, hashtags, image_files, source="creator", status=PENDING):
    """image_files: list of (filename, bytes) tuples. Returns the new draft id."""
    client = _get_client()
    image_urls = [_upload_image(client, filename, data) for filename, data in (image_files or [])]

    draft_id = _new_id()
    row = {
        "id": draft_id,
        "status": status,
        "title": title,
        "content": content,
        "hashtags": ", ".join(hashtags),
        "image_urls": ", ".join(image_urls),
        "source": source,
    }
    try:
        client.table(TABLE).insert(row).execute()
    except Exception as e:
        raise StorageError(f"保存草稿失败: {e}") from e
    return draft_id


def list_drafts():
    client = _get_client()
    try:
        resp = client.table(TABLE).select("*").order("created_at", desc=True).execute()
    except Exception as e:
        raise StorageError(f"读取队列失败: {e}") from e

    drafts = []
    for r in resp.data:
        drafts.append({
            "id": r.get("id"),
            "created_at": r.get("created_at"),
            "status": r.get("status"),
            "title": r.get("title"),
            "content": r.get("content"),
            "hashtags": [h.strip() for h in (r.get("hashtags") or "").split(",") if h.strip()],
            "image_urls": [u.strip() for u in (r.get("image_urls") or "").split(",") if u.strip()],
            "source": r.get("source"),
        })
    return drafts


def update_status(draft_id, status):
    client = _get_client()
    try:
        client.table(TABLE).update({"status": status}).eq("id", draft_id).execute()
    except Exception as e:
        raise StorageError(f"更新状态失败: {e}") from e


def delete_draft(draft_id):
    client = _get_client()
    try:
        client.table(TABLE).delete().eq("id", draft_id).execute()
    except Exception as e:
        raise StorageError(f"删除失败: {e}") from e


def copy_text(draft):
    return draft["title"] + "\n\n" + draft["content"] + "\n\n" + " ".join(f"#{h}" for h in draft["hashtags"])
