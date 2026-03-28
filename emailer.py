"""
Email digest sender.
Sends beautifully formatted HTML email digests of new filings.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text       import MIMEText
from datetime import datetime
import config


SENTIMENT_COLORS = {
    "Positive": "#16a34a",
    "Negative": "#dc2626",
    "Neutral":  "#6b7280",
    "Mixed":    "#d97706",
    "Unknown":  "#6b7280",
}

SENTIMENT_ICONS = {
    "Positive": "▲",
    "Negative": "▼",
    "Neutral":  "●",
    "Mixed":    "◆",
    "Unknown":  "●",
}


def _build_html(summaries: list[dict]) -> str:
    """Build the HTML body for the digest email."""

    filing_blocks = ""
    for s in summaries:
        sentiment     = s.get("sentiment", "Neutral")
        color         = SENTIMENT_COLORS.get(sentiment, "#6b7280")
        icon          = SENTIMENT_ICONS.get(sentiment, "●")
        key_points_li = "".join(f"<li>{p}</li>" for p in s.get("key_points", []))
        filed_str     = s.get("filed", "")
        doc_url       = s.get("document_url", "#")

        filing_blocks += f"""
        <div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;
                    padding:24px;margin-bottom:24px;">
          <!-- Header row -->
          <div style="display:flex;justify-content:space-between;align-items:center;
                      margin-bottom:12px;">
            <div>
              <span style="font-size:22px;font-weight:700;color:#111827;">
                {s['ticker']}
              </span>
              <span style="margin-left:10px;font-size:14px;color:#6b7280;">
                {s['company']}
              </span>
            </div>
            <div>
              <span style="background:{color}15;color:{color};font-weight:600;
                           font-size:13px;padding:4px 12px;border-radius:999px;">
                {icon} {sentiment}
              </span>
            </div>
          </div>

          <!-- Form + date badge -->
          <div style="margin-bottom:14px;">
            <span style="background:#f3f4f6;color:#374151;font-size:12px;font-weight:600;
                         padding:3px 10px;border-radius:4px;letter-spacing:.5px;">
              {s['form']}
            </span>
            <span style="margin-left:8px;font-size:12px;color:#9ca3af;">
              Filed {filed_str}
            </span>
          </div>

          <!-- Headline -->
          <p style="font-size:16px;font-weight:600;color:#1f2937;margin:0 0 12px 0;
                    line-height:1.5;">
            {s.get('headline', '')}
          </p>

          <!-- Key Points -->
          {"<ul style='margin:0 0 12px 0;padding-left:20px;color:#374151;font-size:14px;line-height:1.8;'>" + key_points_li + "</ul>" if key_points_li else ""}

          <!-- Financials -->
          {_optional_block("Financial Highlights", s.get('financials', ''))}

          <!-- Risks -->
          {_optional_block("Risk Factors", s.get('risks', ''), color="#dc2626")}

          <!-- Outlook -->
          {_optional_block("Outlook / Guidance", s.get('outlook', ''), color="#2563eb")}

          <!-- What to Watch -->
          {_optional_block("What to Watch", s.get('action_items', ''), color="#7c3aed")}

          <!-- CTA -->
          <div style="margin-top:16px;">
            <a href="{doc_url}"
               style="font-size:13px;color:#2563eb;text-decoration:none;">
              View full filing →
            </a>
          </div>
        </div>
        """

    date_str = datetime.now().strftime("%B %d, %Y")

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width,initial-scale=1">
    </head>
    <body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,
                 BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
      <div style="max-width:640px;margin:32px auto;padding:0 16px;">

        <!-- Header -->
        <div style="background:linear-gradient(135deg,#1e3a5f,#2563eb);
                    border-radius:12px;padding:28px 32px;margin-bottom:24px;
                    color:#fff;text-align:center;">
          <h1 style="margin:0 0 4px 0;font-size:26px;font-weight:800;
                     letter-spacing:-0.5px;">
            📈 Investor Digest
          </h1>
          <p style="margin:0;font-size:14px;opacity:.8;">{date_str}</p>
          <p style="margin:8px 0 0 0;font-size:13px;opacity:.7;">
            {len(summaries)} new filing{"s" if len(summaries) != 1 else ""} across your portfolio
          </p>
        </div>

        <!-- Filing cards -->
        {filing_blocks if filing_blocks else
         '<p style="text-align:center;color:#6b7280;">No new filings since last check.</p>'}

        <!-- Footer -->
        <div style="text-align:center;padding:16px 0 32px;color:#9ca3af;font-size:12px;">
          <p style="margin:0;">Investor Digest · Powered by AI + SEC EDGAR</p>
          <p style="margin:4px 0 0 0;">
            This digest is for informational purposes only and is not financial advice.
          </p>
        </div>
      </div>
    </body>
    </html>
    """


def _optional_block(label: str, text: str, color: str = "#374151") -> str:
    if not text or not text.strip():
        return ""
    # Convert markdown bullets to readable text
    cleaned = text.strip().replace("**", "")
    return f"""
    <div style="margin-bottom:10px;">
      <span style="font-size:12px;font-weight:700;color:{color};
                   text-transform:uppercase;letter-spacing:.6px;">
        {label}
      </span>
      <p style="margin:4px 0 0 0;font-size:13px;color:#4b5563;line-height:1.6;">
        {cleaned}
      </p>
    </div>
    """


def send_digest(summaries: list[dict], recipient: str = None) -> bool:
    """
    Send the email digest.
    Returns True on success, False on failure.
    """
    to_addr = recipient or config.EMAIL_RECIPIENT
    if not to_addr:
        print("[Email] No recipient configured.")
        return False
    if not config.EMAIL_SENDER or not config.EMAIL_PASSWORD:
        print("[Email] EMAIL_SENDER / EMAIL_PASSWORD not configured.")
        return False

    count    = len(summaries)
    tickers  = ", ".join(sorted({s["ticker"] for s in summaries}))
    subject  = f"📈 Investor Digest: {count} new filing{'s' if count != 1 else ''} — {tickers}"

    html_body  = _build_html(summaries)
    plain_body = _build_plain(summaries)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Investor Digest <{config.EMAIL_SENDER}>"
    msg["To"]      = to_addr

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body,  "html"))

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
            server.sendmail(config.EMAIL_SENDER, to_addr, msg.as_string())
        print(f"[Email] Digest sent to {to_addr} ({count} filings)")
        return True
    except Exception as e:
        print(f"[Email] Failed to send digest: {e}")
        return False


def _build_plain(summaries: list[dict]) -> str:
    lines = [f"INVESTOR DIGEST — {datetime.now().strftime('%B %d, %Y')}", "=" * 50, ""]
    for s in summaries:
        lines.append(f"{s['ticker']} — {s['form']} (Filed {s['filed']})")
        lines.append(s.get("headline", ""))
        for pt in s.get("key_points", []):
            lines.append(f"  • {pt}")
        lines.append(f"  Sentiment: {s.get('sentiment', 'N/A')}")
        lines.append(f"  Full filing: {s.get('document_url', '')}")
        lines.append("")
    lines.append("This digest is for informational purposes only and is not financial advice.")
    return "\n".join(lines)
