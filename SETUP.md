# Investor Digest — Setup Guide

A multi-user SaaS where anyone can sign up, add their stocks, and receive AI-powered SEC filing digests by email.

---

## Deploy in 10 minutes (free, no command line needed)

### Step 1 — Put the code on GitHub
1. Go to **github.com** and create a free account if you don't have one.
2. Click **+** → **New repository** → name it `investor-digest` → click **Create**.
3. Upload all the files in this folder to that repository (drag and drop them in the GitHub UI).

### Step 2 — Deploy on Railway
1. Go to **railway.app** and sign in with your GitHub account.
2. Click **New Project** → **Deploy from GitHub repo**.
3. Select your `investor-digest` repository.
4. Railway will detect the `Procfile` and start building automatically.

### Step 3 — Add your environment variables
In Railway, go to your project → **Variables** tab → add these:

| Variable | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your key from [console.anthropic.com](https://console.anthropic.com/) |
| `EMAIL_SENDER` | Your Gmail address |
| `EMAIL_PASSWORD` | A [Gmail App Password](https://myaccount.google.com/apppasswords) |
| `SECRET_KEY` | Any random string (e.g. `my-super-secret-key-123`) |
| `SEC_USER_AGENT` | `InvestorDigest your@email.com` |

### Step 4 — Go live
Railway gives you a public URL (e.g. `investor-digest.up.railway.app`). Share that link — anyone can sign up and start using it immediately.

---

## Running locally (for testing)

```bash
cd investor-digest
pip install -r requirements.txt
cp .env.example .env   # then fill in your values
python app.py
```
Open **http://localhost:5000**

---

## How users use it

1. They visit your URL and click **Get started free**
2. They sign up with their email and a password
3. They add stock tickers to their portfolio (e.g. AAPL, TSLA)
4. They click **Check All & Email Digest** — the app fetches new SEC filings, summarizes them with AI, and emails a digest
5. The app also checks automatically in the background every 60 minutes

---

## Costs

| Service | Cost |
|---|---|
| Railway hosting | Free tier available (~$5/mo for always-on) |
| Anthropic Claude API | ~$0.01–0.05 per filing summary |
| Gmail SMTP | Free |

For a small number of users the total cost is well under $10/month.
