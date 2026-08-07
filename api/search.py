"""
TITAN Case Search API — Gemini Edition (Free)
Vercel serverless function — fetches real Pakistan cybercrime news
and uses Google Gemini (free) to extract verified case details.
No hallucinations: Gemini is ONLY allowed to use the actual news
text passed to it, not its training data.
"""

import json
import os
import re
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# ── Real, verified Pakistani cybercrime news sources (RSS feeds) ──────────────
NEWS_SOURCES = [
    "https://www.dawn.com/feeds/home",
    "https://arynews.tv/feed/",
    "https://www.nation.com.pk/rss/",
    "https://www.geo.tv/rss",
    "https://propakistani.pk/feed/",
    "https://profit.pakistantoday.com.pk/feed/",
]

CYBERCRIME_KEYWORDS = [
    "nccia", "cyber crime", "cybercrime", "peca", "online fraud",
    "digital arrest", "fia cyber", "fake investment", "blackmail",
    "sim swap", "phishing", "hacking", "online scam", "deepfake",
    "whatsapp fraud", "crypto scam", "fake profile", "identity theft",
    "arrested", "giraftar", "fraud", "scam", "cybercriminal",
]

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent?key={key}"
)


# ── Minimal RSS parser (no external deps) ────────────────────────────────────

def strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def fetch_rss(url: str, limit: int = 10) -> list[dict]:
    articles = []
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "TITAN-Cyber-Guardian/1.0 (educational)"},
        )
        with urllib.request.urlopen(req, timeout=7) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")

        items = re.findall(r"<item>(.*?)</item>", raw, re.S)
        source_match = re.search(r"<title>(.*?)</title>", raw)
        source_name = strip_tags(source_match.group(1)) if source_match else url

        for item in items[:limit]:
            title_m = re.search(r"<title>(.*?)</title>", item, re.S)
            link_m  = re.search(r"<link>(.*?)</link>",  item, re.S)
            desc_m  = re.search(r"<description>(.*?)</description>", item, re.S)
            pub_m   = re.search(r"<pubDate>(.*?)</pubDate>", item, re.S)

            title   = strip_tags(title_m.group(1))  if title_m  else ""
            link    = strip_tags(link_m.group(1))   if link_m   else ""
            snippet = strip_tags(desc_m.group(1))[:500] if desc_m else ""
            pub     = strip_tags(pub_m.group(1))    if pub_m    else "recent"

            blob = (title + " " + snippet).lower()
            if any(kw in blob for kw in CYBERCRIME_KEYWORDS):
                articles.append({
                    "title":   title,
                    "snippet": snippet,
                    "url":     link,
                    "published": pub,
                    "source":  source_name,
                })
    except Exception:
        pass
    return articles


def fetch_all_articles() -> list[dict]:
    all_articles: list[dict] = []
    seen: set[str] = set()
    for url in NEWS_SOURCES:
        for a in fetch_rss(url):
            if a["url"] not in seen:
                seen.add(a["url"])
                all_articles.append(a)
    return all_articles


# ── Gemini call ───────────────────────────────────────────────────────────────

def ask_gemini(user_query: str, articles: list[dict], lang: str) -> dict:
    if not GEMINI_KEY:
        return {"error": "GEMINI_API_KEY not set on server."}

    if not articles:
        return {
            "cases": [],
            "total_found": 0,
            "search_note": "No cybercrime articles found in current RSS feeds.",
            "message": (
                "Koi relevant case nahi mila. NCCIA newsroom directly check karein: https://www.nccia.gov.pk"
                if lang == "ur" else
                "No relevant cases found. Check NCCIA's newsroom directly: https://www.nccia.gov.pk"
            ),
        }

    articles_text = "\n\n---\n\n".join(
        f"SOURCE: {a['source']}\nDATE: {a['published']}\nTITLE: {a['title']}\nURL: {a['url']}\nSNIPPET: {a['snippet']}"
        for a in articles
    )

    lang_note = (
        "Respond in Roman Urdu (Urdu written in English letters, e.g. 'giraftar kiya gaya', 'case darj hua')."
        if lang == "ur" else
        "Respond in English."
    )

    prompt = f"""You are a verified case extraction engine for TITAN, a Pakistani cybercrime victim support tool.

STRICT RULES — follow every one without exception:
1. Extract case details ONLY from the article text provided below. Do NOT use your training data. Do NOT invent names, dates, arrest numbers, money amounts, or law sections.
2. If a detail is not clearly stated in the article, write exactly: "not specified in source"
3. {lang_note}
4. Only include cases relevant to the user query: "{user_query}". Skip unrelated articles entirely.
5. Respond ONLY with a raw JSON object — no markdown, no code fences, no explanation before or after. Exact shape:

{{
  "cases": [
    {{
      "title": "Short descriptive title of the case",
      "date": "Date from article, or 'recent'",
      "location": "City/province if mentioned, else 'Pakistan'",
      "category": "Financial Fraud | Harassment/Blackmail | Account Hacking | SIM Fraud | Fake Officer/Digital Arrest | Fake Profile | Other",
      "peca_sections": "e.g. Section 14, 20 — or 'not specified in source'",
      "summary": "2-3 sentence factual summary using only what the article says",
      "outcome": "Arrests, FIRs, convictions if mentioned — or 'outcome not yet reported'",
      "source_name": "Publication name",
      "source_url": "Full article URL"
    }}
  ],
  "total_found": <integer — number of relevant cases>,
  "search_note": "One sentence: which sources were checked and when"
}}

ARTICLES TO EXTRACT FROM (use ONLY these — nothing else):
{articles_text}
"""

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
    }).encode("utf-8")

    url = GEMINI_URL.format(key=GEMINI_KEY)
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    clean = re.sub(r"```json|```", "", raw_text).strip()
    return json.loads(clean)


# ── Vercel request handler ────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        query  = params.get("q",    [""])[0].strip()
        lang   = params.get("lang", ["en"])[0]

        if not query:
            self._respond(400, {"error": "Missing query parameter 'q'."})
            return

        # 1. Fetch real articles from news RSS feeds
        all_articles = fetch_all_articles()

        # 2. Pre-filter by query keywords (fast client-side before Gemini call)
        q_words = query.lower().split()
        relevant = [
            a for a in all_articles
            if any(w in (a["title"] + " " + a["snippet"]).lower() for w in q_words)
        ]
        # fallback: if nothing pre-matches, send everything and let Gemini decide
        if not relevant:
            relevant = all_articles

        # 3. Ask Gemini to extract structured data from real article text only
        try:
            result = ask_gemini(query, relevant[:14], lang)
        except Exception as e:
            result = {
                "error": f"Gemini extraction failed: {str(e)}",
                "cases": [],
                "total_found": 0,
            }

        result["query"] = query
        self._respond(200, result)

    def do_OPTIONS(self):  # noqa: N802
        self._cors()
        self.end_headers()

    def _cors(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", "application/json")

    def _respond(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
