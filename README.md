# XHS Note Generator · 小红书笔记生成器

Draft 小红书 (XHS) notes fast: upload a few photos, type a few sentences,
get an AI-written title + content + hashtags, run it through a 违禁词
(banned-word) check, preview it, edit if needed, then queue it up.
XHS has no public posting API, so the final "publish" step is still manual —
this just gets you a clean, checked, copy-paste-ready draft in seconds.

Two ways to run this:
- **Just for yourself, locally** — `run.bat`, no cloud setup needed for
  generating/previewing notes. The queue tab needs the Google Sheets backend
  (see below) to actually save anything.
- **With a public link for customers/guests** — `customer_form.py` is a
  separate, simple intake page (upload photos + write a sentence) that
  auto-generates a draft and drops it in your queue. This needs the Google
  Sheets + Drive backend and cloud deployment — see **SETUP_CLOUD.md** for
  the full walkthrough.

## Setup (one time)

1. Get a free Gemini API key: https://aistudio.google.com/apikey
2. Double-click `run.bat`.
   - First run: it creates `.env` from `.env.example` and opens it in
     Notepad — paste your API key after `GEMINI_API_KEY=`, save, close.
   - Run `run.bat` again — it installs dependencies and opens the app in
     your browser (usually `http://localhost:8501`).

(Manual alternative: `pip install -r requirements.txt` then
`streamlit run app.py`.)

## How to use

1. **创建笔记 tab** — upload 1+ photos, type a few sentences about what
   the post is about (a place you visited, a product, an experience...),
   pick a content style, click **🚀 生成笔记**.
2. Edit the generated title/content/hashtags directly if you want.
3. Check the **违禁词检测** section. If anything is flagged, either edit it
   yourself or click **🔄 一键改写违规内容** to have the AI rewrite just the
   flagged parts.
4. Click **✅ 通过审核，加入待发布队列** to save the finished draft (needs
   the Google Sheets backend set up — see SETUP_CLOUD.md).
5. **待发布队列 tab** — every approved draft lives here (including ones
   customers submitted via `customer_form.py`) with its photos, a
   copy-paste-ready text block, and a "标记为已发布" button once you've
   actually posted it in the XHS app.

## Tuning the banned-word list

Edit `banned_words.json` — it has two sections:
- `categories`: plain word/phrase lists, grouped by reason (medical claims,
  absolute/superlative claims, off-platform contact info, scheme language).
- `patterns`: regexes for things like WeChat IDs or phone numbers leaking
  into a post.

Add your own brand-specific banned words to any category — the check is a
simple, deterministic substring/regex scan, so it's instant and easy to
audit (no AI involved in this step).

## Where drafts are stored

In a shared Google Sheet (tab "Queue") + a Google Drive folder for photos —
this is what lets customer submissions (from a separately-hosted
`customer_form.py`) and your own approvals land in the same queue. See
**SETUP_CLOUD.md** for the one-time setup.
