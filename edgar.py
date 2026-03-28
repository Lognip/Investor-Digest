"""
SEC EDGAR API integration.
Fetches filings and press releases for a given stock ticker.
"""

import requests
import time
from bs4 import BeautifulSoup
import config

# SEC requires a User-Agent in the format: "AppName/Version contact@email.com"
# We build it from config but always guarantee a valid fallback.
_sender = config.EMAIL_SENDER or "contact@example.com"
HEADERS = {
    "User-Agent": f"InvestorDigest/1.0 {_sender}",
    "Accept":     "application/json",
}

BASE_URL = "https://data.sec.gov"

# ── In-memory cache so we only download the ticker list once per run ──────────
_ticker_cache: dict | None = None


def _get_ticker_data() -> dict:
    """Download and cache the full SEC ticker → CIK mapping."""
    global _ticker_cache
    if _ticker_cache is not None:
        return _ticker_cache

    url = "https://www.sec.gov/files/company_tickers.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        _ticker_cache = resp.json()
        print(f"[EDGAR] Loaded {len(_ticker_cache)} tickers from SEC EDGAR.")
    except Exception as e:
        print(f"[EDGAR] Could not load ticker list: {e}")
        _ticker_cache = {}
    return _ticker_cache


def _lookup(ticker: str) -> dict | None:
    """Return the SEC entry {ticker, cik_str, title} for a ticker, or None."""
    data = _get_ticker_data()
    t = ticker.upper().strip()
    for entry in data.values():
        if entry.get("ticker", "").upper() == t:
            return entry
    return None


# ── Public helpers ────────────────────────────────────────────────────────────

def get_cik(ticker: str) -> str | None:
    """Return zero-padded 10-digit CIK, or None if not found."""
    entry = _lookup(ticker)
    if entry:
        return str(entry["cik_str"]).zfill(10)
    return None


def get_company_name(ticker: str) -> str:
    """Return the company name for a ticker (falls back to the ticker itself)."""
    entry = _lookup(ticker)
    if entry:
        return entry.get("title", ticker.upper())
    return ticker.upper()


def get_cik_and_name(ticker: str) -> tuple[str | None, str]:
    """Return (cik, company_name) in a single lookup."""
    entry = _lookup(ticker)
    if entry:
        cik  = str(entry["cik_str"]).zfill(10)
        name = entry.get("title", ticker.upper())
        return cik, name
    return None, ticker.upper()


# ── Filing fetcher ────────────────────────────────────────────────────────────

def get_recent_filings(ticker: str, filing_types: list[str] = None,
                       max_results: int = 5) -> list[dict]:
    """
    Return recent filings for a ticker.

    Each item: {ticker, company, form, filed, accession_number,
                description, filing_url, document_url}
    """
    if filing_types is None:
        filing_types = config.FILING_TYPES

    cik, company = get_cik_and_name(ticker)
    if not cik:
        print(f"[EDGAR] No CIK found for ticker: {ticker}")
        return []

    url = f"{BASE_URL}/submissions/CIK{cik}.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[EDGAR] Submissions fetch failed for {ticker}: {e}")
        return []

    recent       = data.get("filings", {}).get("recent", {})
    forms        = recent.get("form", [])
    filed_dates  = recent.get("filingDate", [])
    accessions   = recent.get("accessionNumber", [])
    descriptions = recent.get("primaryDocument", [])

    results = []
    for form, filed, acc, doc in zip(forms, filed_dates, accessions, descriptions):
        if form not in filing_types:
            continue
        acc_clean  = acc.replace("-", "")
        cik_int    = int(cik)
        filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{acc}.txt"
        doc_url    = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{doc}"
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
    """Download and return plain text of a filing (truncated to max_chars)."""
    try:
        time.sleep(0.4)   # polite rate-limiting for SEC servers
        resp = requests.get(document_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")

        if "html" in content_type or document_url.lower().endswith((".htm", ".html")):
            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "ix:nonnumeric", "ix:nonfraction"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
        else:
            text = resp.text

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return "\n".join(lines)[:max_chars]

    except Exception as e:
        print(f"[EDGAR] fetch_filing_text failed ({document_url}): {e}")
        return ""


# ── New-filing detector ───────────────────────────────────────────────────────

def get_new_filings_since(ticker: str, since_date: str,
                          filing_types: list[str] = None) -> list[dict]:
    """Return filings filed strictly after since_date (YYYY-MM-DD)."""
    all_filings = get_recent_filings(ticker, filing_types=filing_types, max_results=20)
    return [f for f in all_filings if f["filed"] > since_date]
