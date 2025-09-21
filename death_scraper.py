#!/usr/bin/env python3
"""
Robust daily death-case scraper (Google News RSS) with detailed terminal logs & progress.
- Interactive: asks for target date (press Enter for today).
- Attempts multiple queries and up to MAX_LINKS_PER_QUERY links each.
- Verbose logging: prints RSS counts, per-link fetch status, reasons for skipping.
- Stops when it has at least MIN_CASES_PER_RUN new records or when limits reached.
- Saves results to scrap_data.json

Run:
  python death_scraper_verbose.py
"""

import re
import json
import time
import argparse
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse, unquote, parse_qs

import requests
from bs4 import BeautifulSoup
import feedparser
from dateutil import parser as dtparser

# -------------------------
# Configurable parameters
# -------------------------
OUTPUT_FILE = "scrap_data.json"
MIN_CASES_PER_RUN = 15
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}

# Queries used (fallback). We restrict to India using site:in and "when:1d" in RSS fetch.
SEARCH_QUERIES = [
    '("death" OR "dead" OR "dies" OR "body found" OR "victim") site:in',
    '("accident" OR "road accident" OR "road crash") site:in',
    '("murder" OR "killed") site:in',
    '("suicide") site:in',
    '("drowned" OR "drowning") site:in',
]

# mapping domain -> short source code for IDs
DOMAIN_SOURCE_MAP = {
    'timesofindia.indiatimes.com': 'TOI',
    'indianexpress.com': 'IE',
    'ndtv.com': 'NDTV',
    'thehindu.com': 'THEHINDU',
    'hindustantimes.com': 'HT',
    'telegraphindia.com': 'TELEGRAPH',
    'news18.com': 'NEWS18',
}

# How many links to request per query (max)
MAX_LINKS_PER_QUERY = 200

# Politeness / speed
REQUEST_TIMEOUT = 10           # seconds per article fetch
DELAY_BETWEEN_REQUESTS = 0.20  # seconds (reduced to speed up)
MAX_TOTAL_LINKS_TO_TRY = 1000  # safety cap across queries
LOG_EVERY_N = 10               # progress log frequency while processing links

# -------------------------
# Helpers
# -------------------------
def parse_iso_date(dt):
    if not dt:
        return None
    try:
        if isinstance(dt, str):
            return dtparser.parse(dt).date().isoformat()
        # feedparser may present time tuple -> try generic parse
        return dtparser.parse(str(dt)).date().isoformat()
    except Exception:
        return None

def resolve_google_link(link):
    """Resolve Google News wrapper links to original URL when possible."""
    if not link:
        return link
    try:
        parsed = urlparse(link)
        if "news.google" in parsed.netloc and parsed.query:
            q = parse_qs(parsed.query).get("url")
            if q:
                return unquote(q[0])
        # Some RSS items may embed the full original link already
    except Exception:
        pass
    # fallback: return as-is
    return link

def google_news_rss_links(query, max_items=200):
    """Fetch Google News RSS for a query and return resolved links (up to max_items)."""
    q = quote_plus(query + " when:1d")
    rss_url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
    print(f"\n[RSS] Fetching RSS for query: {query}")
    print(f"[RSS] URL: {rss_url}")
    feed = feedparser.parse(rss_url)
    n = len(feed.entries)
    print(f"[RSS] feed returned {n} entries (will take up to {max_items})")
    links = []
    for i, entry in enumerate(feed.entries[:max_items], start=1):
        raw_link = entry.get("link")
        resolved = resolve_google_link(raw_link)
        if resolved:
            links.append((resolved, parse_iso_date(getattr(entry, "published", None) or getattr(entry, "published_parsed", None))))
    print(f"[RSS] resolved {len(links)} links from this query")
    return links

def fetch_article_text(url):
    """Fetch article title, text, and meta publish date. Returns (title, text, publish_date_iso)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        return None, None, None, f"request-failed:{e}"
    if resp.status_code != 200:
        return None, None, None, f"status-{resp.status_code}"
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        title = (soup.title.string.strip() if soup.title and soup.title.string else "") or ""
        # gather paragraph text
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        paragraphs = [p for p in paragraphs if len(p) > 30]
        text = " ".join(paragraphs[:8]) if paragraphs else ""
        publish_date = None
        for meta_name in ['article:published_time', 'pubdate', 'date', 'dc.date.issued', 'publishdate', 'timestamp']:
            tag = soup.find("meta", attrs={"property": meta_name}) or soup.find("meta", attrs={"name": meta_name})
            if tag and tag.get("content"):
                publish_date = parse_iso_date(tag.get("content"))
                if publish_date:
                    break
        return title, text, publish_date, "ok"
    except Exception as e:
        return None, None, None, f"parse-error:{e}"

def find_age_gender(text):
    age = None; gender = "Unknown"
    m = re.search(r'\baged?\s*(\d{1,3})\b', text, flags=re.I) or re.search(r'(\d{1,3})[-\s]?year[-\s]?old', text, flags=re.I) or re.search(r'(\d{1,3})\s*years?\s*old', text, flags=re.I)
    if m:
        try:
            age = int(m.group(1))
        except Exception:
            age = None
    if re.search(r'\b(man|male|him|he|boy)\b', text, flags=re.I):
        gender = "Male"
    if re.search(r'\b(woman|female|she|her|girl)\b', text, flags=re.I):
        gender = "Female"
    return age, gender

def find_cause_and_context(text):
    t = (text or "").lower()
    if "accident" in t or "crash" in t: return "accident", text[:300]
    if "suicide" in t: return "suicide", text[:300]
    if "murder" in t or "killed" in t: return "homicide", text[:300]
    if "drown" in t: return "drowning", text[:300]
    if "train" in t and ("hit" in t or "collision" in t): return "train collision", text[:300]
    if "shot" in t or "gunshot" in t: return "gunshot", text[:300]
    if "found dead" in t or "body found" in t: return "found dead", text[:300]
    # fallback: pick first 200 chars
    return "death", (text or "")[:300] or None

def domain_to_source(domain):
    return DOMAIN_SOURCE_MAP.get(domain, domain.upper().split(".")[0])

def normalize_case_id(source_code, date_iso, seq):
    return f"{source_code}-{date_iso}-{seq:03d}"

def load_existing_output(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

# -------------------------
# Main scraping routine
# -------------------------
def run_scrape_interactive():
    # Interactive date input (Enter => today)
    inp = input("Enter the target date (YYYY-MM-DD) or press Enter for today: ").strip()
    if inp:
        try:
            target_date = dtparser.parse(inp).date().isoformat()
        except Exception:
            print("[ERROR] Invalid date format. Use YYYY-MM-DD")
            return
    else:
        target_date = datetime.now(timezone.utc).date().isoformat()

    print(f"[RUN] Target date: {target_date}")
    existing = load_existing_output(OUTPUT_FILE)
    seen_urls = {e.get("source_url") for e in existing if isinstance(e, dict) and e.get("source_url")}
    print(f"[INFO] Already have {len(existing)} records in {OUTPUT_FILE}. Seen URLs={len(seen_urls)}")

    collected = []
    seq_counters = {}
    total_links_tried = 0


