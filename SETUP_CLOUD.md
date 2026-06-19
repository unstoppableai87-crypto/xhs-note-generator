# Cloud setup: shared queue + customer link

This gets you two things:
1. A shared queue (Google Sheets + Drive) so customer submissions and your
   own drafts land in the same place, durably (survives restarts).
2. A public link you can send to customers (`customer_form.py`), separate
   from your own creator tool (`app.py`) — deployed as two small free apps
   on Streamlit Community Cloud.

You'll need a Google account and a (free) GitHub account.

## Part 1 — Google service account (one-time)

1. Go to https://console.cloud.google.com/ and create a new project (or
   reuse one) — name it anything, e.g. "xhs-note-generator".
2. In the search bar, enable these two APIs for that project:
   - **Google Sheets API**
   - **Google Drive API**
3. Go to **APIs & Services → Credentials → Create Credentials → Service account**.
   - Name it anything, e.g. "xhs-note-bot". Skip the optional role/access steps.
4. Open the service account you just created → **Keys** tab → **Add Key →
   Create new key → JSON**. This downloads a `.json` file — keep it private,
   never commit it to git (it's already in `.gitignore` as `service_account.json`).
5. Open that JSON file and copy the `client_email` value (looks like
   `xxx@xxx.iam.gserviceaccount.com`) — you need it in the next part.

## Part 2 — Google Sheet + Drive folder (one-time)

1. Create a new Google Sheet (sheets.new) — name it anything, e.g.
   "XHS Note Queue". Leave it empty; the app creates the "Queue" tab and
   headers automatically on first use.
2. Click **Share** → paste the service account's `client_email` → give it
   **Editor** access → Send (no need to notify).
3. Copy the **Sheet ID** from the URL: `https://docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`.
4. Create a new Google Drive folder (drive.new... or just "New folder" in
   Drive) — this is where uploaded photos will live.
5. Right-click the folder → **Share** → paste the same service account
   email → **Editor** access.
6. Copy the **folder ID** from its URL: `https://drive.google.com/drive/folders/`**`THIS_PART`**.

## Part 3 — test locally first

1. Rename the downloaded JSON key to `service_account.json` and put it in
   this folder (`XHS Note Generator/service_account.json`).
2. In `.env`, fill in:
   ```
   GOOGLE_SHEET_ID=<the sheet ID from step 2.3>
   GOOGLE_DRIVE_FOLDER_ID=<the folder ID from step 2.6>
   CUSTOMER_PASSCODE=<pick any short code, e.g. 22MAC2026>
   ```
3. Run `run.bat`, generate a note, approve it — it should show up in the
   📋 待发布队列 tab with photos loading from Drive links. If you get an
   error mentioning "service_account" or "GOOGLE_SHEET_ID", re-check the
   steps above.

## Part 4 — push to GitHub

Streamlit Community Cloud deploys from a GitHub repo. Ask your assistant to
run `git init`, commit, create a GitHub repo, and push — or do it yourself:

```
git init
git add -A
git commit -m "XHS Note Generator"
gh repo create xhs-note-generator --private --source=. --push
```

`service_account.json` and `.env` are already gitignored, so your secrets
won't be pushed. **Use a private repo** since the code references your
Sheet/Drive setup.

## Part 5 — deploy two apps on Streamlit Community Cloud

Go to https://share.streamlit.io → sign in with GitHub → **New app**, twice:

**App 1 — your creator tool (for yourself)**
- Repo: the one you just pushed · Branch: main · Main file path: `app.py`
- After it deploys, go to **Settings → Secrets** and paste (filling in your
  real values — for `GOOGLE_SERVICE_ACCOUNT_JSON`, open your downloaded
  JSON key file and paste its *entire contents* as one line inside the
  triple quotes):
  ```toml
  GEMINI_API_KEY = "your-gemini-key"
  GEMINI_MODEL = "gemini-2.5-flash"
  GOOGLE_SHEET_ID = "your-sheet-id"
  GOOGLE_DRIVE_FOLDER_ID = "your-folder-id"
  GOOGLE_SERVICE_ACCOUNT_JSON = '''{"type": "service_account", ...}'''
  CUSTOMER_PASSCODE = "22MAC2026"
  ```
- Save — this is your own bookmark. No need to share this URL with guests.

**App 2 — the customer form (the link you send out)**
- Same repo and branch · Main file path: `customer_form.py`
- Same secrets as above (both apps share the same Sheet/Drive/passcode).
- This app's URL is the one you give to customers/guests.

That's it — guests open App 2's link, enter the passcode, upload photos,
write a few sentences, submit. It shows up in App 1's 📋 待发布队列 tab for
you to review, edit, run the 违禁词 check, and approve.

## Notes

- Streamlit Community Cloud's free tier sleeps apps after inactivity; they
  wake up automatically (with a ~30s cold start) when someone opens the
  link — no action needed from you.
- If you ever rotate the Gemini key or change the passcode, update it in
  **both** apps' Secrets (Settings → Secrets → edit → Save, which restarts
  the app).
