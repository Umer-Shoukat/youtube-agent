# 🎯 YouTube Creator Digest Agent

Automatically analyzes top business podcasters' latest YouTube videos daily using Claude Haiku, then emails you:
- **5 video ideas** (with hooks + why they work)
- **2–3 business ideas** (with market, revenue model, and timing)
- **Trending themes** from today's creator content

**Cost: ~$0.05–0.20/day | Runs 100% automatically via GitHub Actions**

---

## 📺 Channels Tracked

| Creator | Podcast/Channel |
|---|---|
| Alex Hormozi | The Game |
| Leila Hormozi | Build |
| Nathan Barry | Nathan Barry |
| Chamath, Jason, Sacks, Friedberg | All-In Podcast |
| Patrick Bet-David | PBD |
| — | TBPN |
| — | Operators Podcast |
| Sam Parr & Shaan Puri | My First Million |
| Dan Martell | The Martell Method |
| David Senra | Founders |
| Steven Bartlett | DOAC |
| Chris Williamson | Modern Wisdom |
| — | Chew the Fat / Founders Table |

---

## 🚀 Setup Guide (5 Steps)

### Step 1 — Fork/Clone this Repo
```bash
git clone https://github.com/YOUR_USERNAME/youtube-agent.git
cd youtube-agent
```

### Step 2 — Get Your API Key
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an API key (add $5 credit — lasts months at this usage level)

### Step 3 — Set Up Gmail App Password
1. Go to your Google Account → Security
2. Enable **2-Step Verification** (required)
3. Search for **App Passwords** → Generate one for "Mail"
4. Copy the 16-character password (e.g. `abcd efgh ijkl mnop`)

### Step 4 — Add GitHub Secrets
In your GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**

Add these 4 secrets:

| Secret Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (sk-ant-...) |
| `GMAIL_USER` | Your Gmail address (you@gmail.com) |
| `GMAIL_APP_PASSWORD` | The 16-char app password from Step 3 |
| `EMAIL_RECIPIENT` | Where to send the digest (can be same email) |

### Step 5 — Push and Activate
```bash
git add .
git commit -m "Initial setup"
git push origin main
```

Then go to **Actions tab** in GitHub → click **"Daily Creator Digest"** → **"Run workflow"** to test it immediately!

---

## ⏰ Schedule
Runs daily at **7:00 AM Pakistan time (PKT)** automatically.

To change the time, edit this line in `.github/workflows/daily_digest.yml`:
```yaml
- cron: "0 2 * * *"   # 2:00 AM UTC = 7:00 AM PKT
```
Use [crontab.guru](https://crontab.guru) to generate your preferred time.

---

## ➕ Adding New Channels
Open `channels.py` and add a new entry:
```python
{
    "name": "Gary Vaynerchuk - GaryVee",
    "handle": "@GaryVee",
    "url": "https://www.youtube.com/@GaryVee",
},
```
Commit and push — it's live immediately.

---

## 🗂 Project Structure
```
youtube-agent/
├── agent.py          # Main agent logic
├── channels.py       # Channel list — edit this to add/remove creators
├── requirements.txt  # Python dependencies
├── README.md
└── .github/
    └── workflows/
        └── daily_digest.yml  # GitHub Actions schedule
```

---

## 💰 Cost Breakdown
| Component | Cost |
|---|---|
| YouTube transcripts | Free |
| Claude Haiku (~26 videos × 4k chars + 2k output) | ~$0.05–0.15/day |
| GitHub Actions (2000 free mins/month) | Free |
| Gmail SMTP | Free |
| **Total** | **~$1.50–4.50/month** |
