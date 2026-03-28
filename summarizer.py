"""
AI summarization engine using Anthropic Claude.
Extracts investor-relevant insights from SEC filings and press releases.
"""

import anthropic
import config

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not config.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not set in your .env file.")
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


SYSTEM_PROMPT = """You are an expert financial analyst assistant specializing in extracting
actionable investor insights from SEC filings and corporate press releases.

Your job is to read raw filing text and produce a concise, structured summary that helps
a retail investor quickly understand what matters.

Always be factual. Never speculate. Flag anything that seems like a material risk or opportunity."""


def summarize_filing(
    company: str,
    ticker: str,
    form_type: str,
    filed_date: str,
    filing_text: str,
) -> dict:
    """
    Summarize a filing and return a structured dict with investor-relevant insights.

    Returns:
    {
        "headline":      one-line summary,
        "key_points":    list of 3-6 bullet points,
        "financials":    revenue/earnings highlights (if present),
        "risks":         notable risk factors mentioned,
        "outlook":       forward guidance or management comments,
        "sentiment":     "Positive" | "Neutral" | "Negative" | "Mixed",
        "action_items":  what an investor might want to watch or do,
        "raw_summary":   full markdown summary
    }
    """
    prompt = f"""
Company: {company} ({ticker})
Filing Type: {form_type}
Filed: {filed_date}

--- FILING TEXT (truncated) ---
{filing_text[:10000]}
--- END ---

Please analyze this {form_type} filing and provide:

1. **Headline** (1 sentence): The single most important thing an investor needs to know.
2. **Key Points** (3-6 bullets): Most material facts — revenue, earnings, guidance, major events.
3. **Financial Highlights**: Any revenue, EPS, margin, or cash flow figures mentioned.
4. **Risk Factors**: Any new or notable risks flagged in this filing.
5. **Outlook / Guidance**: What management said about the future, if anything.
6. **Sentiment**: Is the overall tone of this filing Positive, Negative, Neutral, or Mixed for investors?
7. **What to Watch**: 1-2 things an investor should monitor after reading this.

Format your response with clear markdown headings. Be concise — the investor is busy.
"""

    try:
        client = _get_client()   # inside try so key errors are caught gracefully
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            system=SYSTEM_PROMPT,
        )
        raw = message.content[0].text

        # Parse structured fields from the markdown
        result = {
            "headline":     _extract_section(raw, "Headline", single_line=True),
            "key_points":   _extract_bullets(raw, "Key Points"),
            "financials":   _extract_section(raw, "Financial Highlights"),
            "risks":        _extract_section(raw, "Risk Factors"),
            "outlook":      _extract_section(raw, "Outlook"),
            "sentiment":    _extract_sentiment(raw),
            "action_items": _extract_section(raw, "What to Watch"),
            "raw_summary":  raw,
        }
        return result

    except Exception as e:
        print(f"[Summarizer] Failed to summarize {ticker} {form_type}: {e}")
        return {
            "headline":     f"Summary unavailable for {company} {form_type}",
            "key_points":   [],
            "financials":   "",
            "risks":        "",
            "outlook":      "",
            "sentiment":    "Unknown",
            "action_items": "",
            "raw_summary":  f"Error generating summary: {e}",
        }


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _extract_section(text: str, heading: str, single_line: bool = False) -> str:
    """Extract content under a markdown heading.
    Matches headings that START WITH the given keyword, so 'Outlook' will
    match both '## Outlook' and '## Outlook / Guidance'.
    """
    import re
    # [^\n#]* allows " / Guidance" or ": " suffixes after the keyword
    pattern = rf"#+\s*{re.escape(heading)}[^\n#]*\n(.*?)(?=\n#+\s|\Z)"
    match   = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    content = match.group(1).strip()
    if single_line:
        content = content.splitlines()[0].strip().lstrip("*").strip()
    return content


def _extract_bullets(text: str, heading: str) -> list[str]:
    """Extract a bullet-point list under a heading."""
    section = _extract_section(text, heading)
    bullets = []
    for line in section.splitlines():
        line = line.strip()
        if line.startswith(("-", "*", "•", "·")) or (len(line) > 2 and line[0].isdigit() and line[1] in ".):"):
            clean = line.lstrip("-*•·0123456789.)").strip()
            if clean:
                bullets.append(clean)
    return bullets


def _extract_sentiment(text: str) -> str:
    """Extract the sentiment label."""
    import re
    match = re.search(r"sentiment[:\s]+(positive|negative|neutral|mixed)", text, re.IGNORECASE)
    if match:
        return match.group(1).capitalize()
    for word in ["Positive", "Negative", "Neutral", "Mixed"]:
        if word.lower() in text.lower():
            return word
    return "Neutral"
