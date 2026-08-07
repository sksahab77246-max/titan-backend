"""
TITAN Daily Refresh — Gemini Edition
Vercel cron job (runs daily at 06:00 UTC).
Checks all RSS feeds and logs how many cybercrime articles were found.
"""
import json
import re
import urllib.request
from http.server import BaseHTTPRequestHandler

NEWS_SOURCES = [
    "https://www.dawn.com/feeds/home",
    "https://arynews.tv/feed/",
    "https://www.nation.com.pk/rss/",
    "https://www.geo.tv/rss",
    "https://propakistani.pk/feed/",
    "https://profit.pakistantoday.com.pk/feed/",
]
KEYWORDS = [
    "nccia","cybercrime","cyber crime","peca","online fraud","digital arrest",
    "phishing","fake investment","blackmail","sim swap","hacking","online scam",
]

def strip_tags(h):
    return re.sub(r"<[^>]+>"," ",h).strip()

class handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        found, log = 0, []
        for url in NEWS_SOURCES:
            try:
                req = urllib.request.Request(url, headers={"User-Agent":"TITAN/1.0"})
                with urllib.request.urlopen(req, timeout=7) as r:
                    raw = r.read().decode("utf-8","ignore")
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
        body = json.dumps({"status":"ok","found":found,"sample":log[:10]},
                          ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self,*a):
        pass
