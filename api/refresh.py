import json
import os
import re
import urllib.request


NEWS_SOURCES = [
    "https://www.dawn.com/feeds/home",
    "https://arynews.tv/feed/",
    "https://www.nation.com.pk/rss/",
    "https://www.geo.tv/rss",
    "https://propakistani.pk/feed/",
]
KEYWORDS = [
    "nccia","cybercrime","cyber crime","peca","online fraud",
    "digital arrest","phishing","fake investment","blackmail","hacking",
]

def strip_tags(h):
    return re.sub(r"<[^>]+>", " ", h).strip()

def handler(request, response):
    found, log = 0, []
    for url in NEWS_SOURCES:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TITAN/1.0"})
            with urllib.request.urlopen(req, timeout=7) as r:
                raw = r.read().decode("utf-8", "ignore")
            items = re.findall(r"<item>(.*?)</item>", raw, re.S)
            src = re.search(r"<title>(.*?)</title>", raw)
            src_name = strip_tags(src.group(1)) if src else url
            for item in items[:10]:
                t = re.search(r"<title>(.*?)</title>", item, re.S)
                title = strip_tags(t.group(1)) if t else ""
                if any(k in title.lower() for k in KEYWORDS):
                    found += 1
                    log.append(f"{src_name}: {title[:80]}")
        except Exception as e:
            log.append(f"ERROR {url}: {e}")
    return response.json({
        "status": "ok",
        "found": found,
        "sample": log[:10]
    })
