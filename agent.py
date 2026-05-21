"""
YouTube Influencer Digest Agent
================================
Fetches recent videos from top business podcasters, extracts transcripts,
analyzes with Claude Haiku, and emails a daily digest with:
  - 5 video ideas for your own channel
  - 2-3 business ideas inspired by today's content
"""



import os
import re
import json
import smtplib
import traceback
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

from channels import CHANNELS, VIDEOS_PER_CHANNEL, MAX_TRANSCRIPT_CHARS


# ─────────────────────────────────────────────
# 1. FETCH LATEST VIDEOS FROM A CHANNEL
# ─────────────────────────────────────────────
def _get_youtube_client():
    return build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])


def get_recent_videos(channel_url: str, channel_name: str, limit: int = 2) -> list[dict]:
    """Return the most recent `limit` videos using the YouTube Data API v3."""
    videos = []
    try:
        youtube = _get_youtube_client()

        # Extract @handle from URL e.g. https://www.youtube.com/@AlexHormozi
        handle = channel_url.split("/@")[-1] if "/@" in channel_url else None
        if not handle:
            print(f"  ⚠️  {channel_name}: could not parse handle from URL")
            return videos

        # Resolve handle → uploads playlist ID (costs 1 API unit)
        ch_resp = youtube.channels().list(
            part="contentDetails",
            forHandle=handle
        ).execute()

        items = ch_resp.get("items", [])
        if not items:
            print(f"  ⚠️  {channel_name}: channel not found for handle @{handle}")
            return videos

        uploads_playlist = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

        # Fetch recent videos from uploads playlist (costs 1 API unit)
        pl_resp = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist,
            maxResults=limit
        ).execute()

        for item in pl_resp.get("items", []):
            snippet = item["snippet"]
            video_id = snippet["resourceId"]["videoId"]
            title = snippet.get("title", video_id)
            videos.append({
                "id": video_id,
                "title": title,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "channel": channel_name,
            })

        print(f"  ✅ {channel_name}: {len(videos)} video(s) found")
    except Exception as e:
        print(f"  ⚠️  {channel_name}: could not fetch videos — {e}")
    return videos


# ─────────────────────────────────────────────
# 2. GET TRANSCRIPT FOR A VIDEO
# ─────────────────────────────────────────────
def get_transcript(video_id: str, max_chars: int = MAX_TRANSCRIPT_CHARS) -> str:
    """Fetch and truncate a YouTube transcript. Returns empty string on failure."""
    try:
        segments = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])
        full_text = " ".join(s["text"] for s in segments)
        # Clean up whitespace artifacts
        full_text = re.sub(r"\s+", " ", full_text).strip()
        return full_text[:max_chars]
    except (TranscriptsDisabled, NoTranscriptFound):
        return ""
    except Exception as e:
        print(f"    Transcript error for {video_id}: {e}")
        return ""


# ─────────────────────────────────────────────
# 3. COLLECT ALL CONTENT FROM ALL CHANNELS
# ─────────────────────────────────────────────
def collect_content() -> list[dict]:
    """Loop over all channels, grab recent videos + transcripts."""
    print("\n📡 Fetching videos from all channels...\n")
    collected = []

    for ch in CHANNELS:
        videos = get_recent_videos(ch["url"], ch["name"], limit=VIDEOS_PER_CHANNEL)
        for v in videos:
            transcript = get_transcript(v["id"])
            v["transcript"] = transcript
            v["has_transcript"] = bool(transcript)
            collected.append(v)

    total = len(collected)
    with_transcript = sum(1 for v in collected if v["has_transcript"])
    print(f"\n📊 Collected {total} videos | {with_transcript} have transcripts\n")
    return collected


# ─────────────────────────────────────────────
# 4. BUILD THE PROMPT FOR CLAUDE
# ─────────────────────────────────────────────
def build_prompt(videos: list[dict]) -> str:
    sections = []
    for v in videos:
        content = v["transcript"] if v["has_transcript"] else "(No transcript available)"
        sections.append(
            f"### {v['channel']}\n"
            f"**Video:** {v['title']}\n"
            f"**URL:** {v['url']}\n"
            f"**Transcript excerpt:** {content}\n"
        )

    content_block = "\n\n".join(sections)

    prompt = f"""You are an expert business content strategist and entrepreneur advisor.

Below is a curated set of transcripts from today's top business podcasters and influencers.
Deeply analyze the themes, insights, frameworks, and trends discussed.

---
{content_block}
---

Based on your analysis, produce EXACTLY the following output in this format:

=== VIDEO IDEAS ===

1. [TITLE]: <Compelling, SEO-friendly YouTube title>
   [HOOK]: <First 30-second script hook that grabs attention>
   [WHY IT WORKS]: <1 sentence on why this will perform well>

2. [TITLE]: ...
   [HOOK]: ...
   [WHY IT WORKS]: ...

3. [TITLE]: ...
   [HOOK]: ...
   [WHY IT WORKS]: ...

4. [TITLE]: ...
   [HOOK]: ...
   [WHY IT WORKS]: ...

5. [TITLE]: ...
   [HOOK]: ...
   [WHY IT WORKS]: ...

=== BUSINESS IDEAS ===

1. [CONCEPT]: <Name of business idea>
   [TARGET MARKET]: <Who this is for>
   [REVENUE MODEL]: <How it makes money>
   [WHY NOW]: <What trend or insight from today's content makes this timely>

2. [CONCEPT]: ...
   [TARGET MARKET]: ...
   [REVENUE MODEL]: ...
   [WHY NOW]: ...

3. [CONCEPT]: ...
   [TARGET MARKET]: ...
   [REVENUE MODEL]: ...
   [WHY NOW]: ...

=== TRENDING THEMES ===
List 3-5 key recurring themes or insights from today's content in bullet points.

Be specific, actionable, and business-focused. Avoid generic advice."""

    return prompt


# ─────────────────────────────────────────────
# 5. CALL CLAUDE HAIKU
# ─────────────────────────────────────────────
def analyze_with_claude(prompt: str) -> str:
    """Send prompt to Claude Haiku and return the response text."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print("🤖 Sending to Claude Haiku for analysis...")
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ─────────────────────────────────────────────
# 6. BUILD HTML EMAIL
# ─────────────────────────────────────────────
def build_email_html(analysis: str, videos: list[dict]) -> str:
    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")

    # Parse sections from Claude output
    def extract_section(text, start_marker, end_marker=None):
        start = text.find(start_marker)
        if start == -1:
            return ""
        start += len(start_marker)
        if end_marker:
            end = text.find(end_marker, start)
            return text[start:end].strip() if end != -1 else text[start:].strip()
        return text[start:].strip()

    video_ideas_raw = extract_section(analysis, "=== VIDEO IDEAS ===", "=== BUSINESS IDEAS ===")
    business_ideas_raw = extract_section(analysis, "=== BUSINESS IDEAS ===", "=== TRENDING THEMES ===")
    themes_raw = extract_section(analysis, "=== TRENDING THEMES ===")

    def format_section_html(raw_text):
        """Convert numbered list with [KEY]: value format to styled HTML."""
        html = ""
        items = re.split(r"\n(?=\d+\.)", raw_text.strip())
        for item in items:
            if not item.strip():
                continue
            lines = item.strip().split("\n")
            html += '<div style="background:#f9f9f9;border-left:4px solid #1a73e8;padding:14px 18px;margin-bottom:16px;border-radius:4px;">'
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Bold the key labels like [TITLE]:
                line = re.sub(r"\[([A-Z\s]+)\]:", r"<strong>[\1]:</strong>", line)
                html += f"<p style='margin:4px 0;font-size:14px;color:#333;'>{line}</p>"
            html += "</div>"
        return html

    def format_themes_html(raw_text):
        lines = [l.strip().lstrip("-•*").strip() for l in raw_text.split("\n") if l.strip()]
        items = "".join(f"<li style='margin-bottom:8px;'>{l}</li>" for l in lines if l)
        return f"<ul style='padding-left:20px;'>{items}</ul>"

    # Build sources table
    sources_rows = ""
    for v in videos[:10]:
        icon = "✅" if v["has_transcript"] else "⚪"
        sources_rows += f"""
        <tr>
          <td style="padding:6px 10px;font-size:13px;color:#555;">{icon} {v['channel']}</td>
          <td style="padding:6px 10px;font-size:13px;">
            <a href="{v['url']}" style="color:#1a73e8;text-decoration:none;">{v['title'][:70]}{'...' if len(v['title'])>70 else ''}</a>
          </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;background:#fff;">

  <!-- HEADER -->
  <div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);padding:30px;border-radius:10px;margin-bottom:24px;text-align:center;">
    <h1 style="color:#fff;margin:0;font-size:24px;letter-spacing:1px;">🎯 Daily Creator Digest</h1>
    <p style="color:#a0aec0;margin:8px 0 0;font-size:14px;">{today} — Powered by Claude Haiku</p>
  </div>

  <!-- VIDEO IDEAS -->
  <div style="margin-bottom:28px;">
    <h2 style="color:#1a1a2e;border-bottom:2px solid #1a73e8;padding-bottom:8px;font-size:18px;">
      🎬 5 Video Ideas for Your Channel
    </h2>
    {format_section_html(video_ideas_raw)}
  </div>

  <!-- BUSINESS IDEAS -->
  <div style="margin-bottom:28px;">
    <h2 style="color:#1a1a2e;border-bottom:2px solid #34a853;padding-bottom:8px;font-size:18px;">
      💡 Business Ideas from Today's Content
    </h2>
    {format_section_html(business_ideas_raw)}
  </div>

  <!-- TRENDING THEMES -->
  <div style="margin-bottom:28px;">
    <h2 style="color:#1a1a2e;border-bottom:2px solid #fbbc04;padding-bottom:8px;font-size:18px;">
      🔥 Trending Themes Today
    </h2>
    <div style="background:#fffbf0;padding:16px 20px;border-radius:6px;">
      {format_themes_html(themes_raw)}
    </div>
  </div>

  <!-- SOURCES -->
  <div style="margin-bottom:28px;">
    <h2 style="color:#1a1a2e;border-bottom:2px solid #ea4335;padding-bottom:8px;font-size:18px;">
      📺 Today's Sources Analyzed
    </h2>
    <table style="width:100%;border-collapse:collapse;">
      {sources_rows}
    </table>
  </div>

  <!-- FOOTER -->
  <div style="text-align:center;padding:20px;color:#888;font-size:12px;border-top:1px solid #eee;">
    <p>Generated automatically by your YouTube Influencer Agent 🤖</p>
    <p>Running on GitHub Actions • Powered by Claude Haiku • Cost: ~$0.01/day</p>
  </div>

</body>
</html>"""
    return html


# ─────────────────────────────────────────────
# 7. SEND EMAIL VIA GMAIL SMTP
# ─────────────────────────────────────────────
def send_email(html_body: str, subject: str):
    sender = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ["EMAIL_RECIPIENT"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Creator Digest Agent <{sender}>"
    msg["To"] = recipient

    msg.attach(MIMEText(html_body, "html"))

    print(f"📧 Sending email to {recipient}...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
    print("✅ Email sent successfully!")


# ─────────────────────────────────────────────
# 8. MAIN
# ─────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  🚀 YouTube Creator Digest Agent Starting...")
    print("=" * 55)

    try:
        # Step 1: Collect videos + transcripts
        videos = collect_content()

        if not videos:
            print("❌ No videos collected. Exiting.")
            return

        # Step 2: Build prompt
        prompt = build_prompt(videos)

        # Step 3: Analyze with Claude
        analysis = analyze_with_claude(prompt)
        print("\n✅ Analysis complete!\n")
        print(analysis[:500] + "...\n")

        # Step 4: Build email
        today_str = datetime.now(timezone.utc).strftime("%b %d, %Y")
        subject = f"🎯 Daily Creator Digest — {today_str}"
        html = build_email_html(analysis, videos)

        # Step 5: Send email
        send_email(html, subject)

        print("\n🎉 Done! Check your inbox.")

    except Exception as e:
        print(f"\n❌ Agent failed: {e}")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
