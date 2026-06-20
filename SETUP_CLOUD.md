# Cloud setup: shared queue + customer link

This gets you two things:
1. A shared queue (Supabase) so guest submissions and your own drafts land
   in the same place, durably (survives restarts). Supabase's free tier
   needs only an email to sign up — no credit card.
2. One public link (`app.py`, deployed to Streamlit Community Cloud) that
   serves both roles — admin and guest get the same 创建笔记/封面图
   features, but only admin sees 📋 待发布队列. Role is decided purely by
   which passcode you type in.

You'll need an email address and a (free) GitHub account (already set up).

## Part 1 — create a Supabase project (one-time)

1. Go to https://supabase.com → **Start your project** → sign up with
   email or GitHub (no card required for the free tier).
2. **New project** → name it anything, e.g. `xhs-note-generator` → pick any
   region close to you → set a database password (save it somewhere, you
   likely won't need it again) → **Create new project**. Wait ~1 minute
   for it to finish provisioning.

## Part 2 — create the queue table

1. In your project, open the left sidebar → **SQL Editor** → **New query**.
2. Paste this and click **Run**:
   ```sql
   create table queue (
     id text primary key,
     created_at timestamptz default now(),
     status text,
     title text,
     content text,
     hashtags text,
     image_urls text,
     source text
   );
   ```
   This creates the table the app reads/writes (one row per draft note).

## Part 3 — create the photo storage bucket

1. Left sidebar → **Storage** → **New bucket**.
2. Name it `photos` → toggle **Public bucket** to ON (so the app can show
   photos without extra signing) → **Create bucket**.

## Part 4 — get your API credentials

1. Left sidebar → **Project Settings** (gear icon) → **API**.
2. Copy the **Project URL** (looks like `https://xxxxx.supabase.co`).
3. Copy the **`service_role` key** (under "Project API keys" — NOT the
   `anon` key; the service_role key is what lets the app write to the
   queue). Keep this private, never commit it to git.

## Part 5 — test locally first

In `.env`, fill in:
```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=<your service_role key>
SUPABASE_BUCKET=photos
CUSTOMER_PASSCODE=<pick any short code, e.g. 22MAC2026>
```
Run `run.bat`, generate a note, approve it — it should show up in the
📋 待发布队列 tab with photos loading from Supabase. If you get an error
mentioning "SUPABASE_URL" or "保存草稿失败", re-check the steps above
(common cause: used the `anon` key instead of `service_role`).

## Part 6 — push to GitHub

Already done — this project is pushed to
`https://github.com/unstoppableai87-crypto/xhs-note-generator` (private repo).
If you make more local changes, ask your assistant to commit and push again.

## Part 7 — deploy one app on Streamlit Community Cloud

Go to https://share.streamlit.io → sign in with GitHub → **New app**:

- Repo: `unstoppableai87-crypto/xhs-note-generator` · Branch: master ·
  Main file path: `app.py`
- After it deploys, go to **Settings → Secrets** and paste (filling in your
  real values):
  ```toml
  GEMINI_API_KEY = "your-gemini-key"
  GEMINI_MODEL = "gemini-2.5-flash"
  SUPABASE_URL = "https://xxxxx.supabase.co"
  SUPABASE_KEY = "your-service-role-key"
  SUPABASE_BUCKET = "photos"
  CUSTOMER_PASSCODE = "magisionhair"
  CREATOR_PASSCODE = "magisionhair1203"
  ```
- Save — the app restarts and will now ask for a passcode before showing
  anything. Enter `CREATOR_PASSCODE`'s value yourself to get full access
  including 📋 待发布队列; share `CUSTOMER_PASSCODE`'s value with guests so
  they get 创建笔记/封面图 only.

That's it — there's only one URL. You and your guests both open it; the
passcode you each type in decides what you see. Guest-submitted drafts
land in the same 📋 待发布队列 you see, tagged "👤 客户提交".

## Notes

- Streamlit Community Cloud's free tier sleeps apps after inactivity; they
  wake up automatically (with a ~30s cold start) when someone opens the
  link — no action needed from you.
- If you ever rotate the Gemini key or either passcode, update it in
  **Settings → Secrets → edit → Save**, which restarts the app.
- Supabase's free tier pauses a project after 1 week with zero activity —
  opening the app once reactivates it (may take a minute the first time).
