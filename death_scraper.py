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

