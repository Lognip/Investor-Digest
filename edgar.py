"""
SEC EDGAR API integration.
Fetches filings and press releases for a given stock ticker.
"""

import requests
import time
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import config

HEADERS = {"User-Agent": config.SEC_USER_AGENT or "InvestorDigest contact@example.com"}
BASE_URL = "https://data.sec.gov"
EFTS_URL = "https://efts.sec.gov/LATEST/search-index"


# ── Ticker → CIK lookup ──────────────────────────────────────────────────────

def get_cik(ticker: str) -> str | None:
    """Return zero-padded 10-digit CIK for a ticker, or None if not found."""
    url = "https://www.sec.gov/files/company_tickers.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for entry in data.values():
            if entry["ticker"].upper() == ticker.upper():
                return str(entry["cik_str"]).zfill(10)
    except Exception as e:
        print(f"[EDGAR] CIK lookup failed for {ticker}: {e}")
    return None


def get_company_name(ticker: str) -> str:
    """Return the company name for a ticker."""
    url = "https://www.sec.gov/files/company_tickers.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for entry in data.values():
            if entry["ticker"].upper() == ticker.upper():
                return entry["title"]
    except Exception:
        pass
    return ticker.upper()


# ── Filing fetcher ────────────────────────────────────────────────────────────

def get_recent_filings(ticker: str, filing_types: list[str] = None, max_results: int = 5) -> list[dict]:
    """
    Return recent filings for a ticker.

    Each item: {
        "ticker", "company", "form", "filed", "accession_number",
        "description", "filing_url", "document_url"
    }
    """
    if filing_types is None:
        filing_types = config.FILING_TYPES

    cik = get_cik(ticker)
    if not cik:
        print(f"[EDGAR] Could not find CIK for ticker: {ticker}")
        return []

    company = get_company_name(ticker)
    url = f"{BASE_URL}/submissions/CIK{cik}.json"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[EDGAR] Submissions fetch failed for {ticker}: {e}")
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms        = recent.get("form", [])
    filed_dates  = recent.get("filingDate", [])
    accessions   = recent.get("accessionNumber", [])
    descriptions = recent.get("primaryDocument", [])

    results = []
    for form, filed, acc, doc in zip(forms, filed_dates, accessions, descriptions):
        if form not in filing_types:
            continue
        acc_clean  = acc.replace("-", "")
        filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{acc}.txt"
        doc_url    = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{doc}"
        results.append({
            "ticker":           ticker.upper(),
            "company":          company,
            "form":             form,
            "filed":            filed,
            "accession_number": acc,
            "description":      doc,
            "filing_url":       filing_url,
            "document_url":     doc_url,
        })
        if len(results) >= max_results:
            break

    return results


# ── Full-text fetcher ─────────────────────────────────────────────────────────

def fetch_filing_text(document_url: str, max_chars: int = 12000) -> str:
    """
    Download and return plain text of a filing document (truncated to max_chars).
    Strips HTML tags if the document is HTML.
    """
    try:
        time.sleep(0.5)   # be polite to SEC servers
        resp = requests.get(document_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")

        if "html" in content_type or document_url.endswith((".htm", ".html")):
            soup = BeautifulSoup(resp.text, "lxml")
            # Remove script / style / inline XBRL noise
            for tag in soup(["script", "style", "ix:nonnumeric", "ix:nonfraction"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
        else:
            text = resp.text

        # Collapse whitespace
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        text  = "\n".join(lines)
        return text[:max_chars]

    except Exception as e:
        print(f"[EDGAR] fetch_filing_text failed for {document_url}: {e}")
        return ""


# ── New-filing detector ───────────────────────────────────────────────────────

def get_new_filings_since(ticker: str, since_date: str, filing_types: list[str] = None) -> list[dict]:
    """
    Return filings filed after `since_date` (YYYY-MM-DD string).
    """
    all_filings  = get_recent_filings(ticker, filing_types=filing_types, max_results=20)
    new_filings  = [f for f in all_filings if f["filed"] > since_date]
    return new_filings
