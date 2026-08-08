import json
import os
import re
import urllib.request
from urllib.parse import parse_qs, urlparse

NEWS_SOURCES = [
    "https://www.dawn.com/feeds/home",
    "https://arynews.tv/feed/",
    "https://www.nation.com.pk/rss/",
    "https://www.geo.tv/rss",
    "https://propakistani.pk/feed/",
    "https://profit.pakistantoday.com.pk/feed/",
]

CYBERCRIME_KEYWORDS = [
    "nccia","cyber crime","cybercrime","peca","online fraud",
    "digital arrest","fia cyber","fake investment","blackmail",
    "sim swap","phishing","hacking","online scam","whatsapp fraud",
    "crypto scam","fake profile","identity theft","arrested","fraud","scam",
]

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"


def strip_tags(html):
    return re.sub(r"<[^>]+>", " ", html).strip()


def fetch_rss(url, limit=10):
    articles = []
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "TITAN-Cyber-Guardian/1.0"}
        )
        with urllib.request.urlopen(req, timeout=7) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        items = re.findall(r"<item>(.*?)</item>", raw, re.S)
        src = re.search(r"<title>(.*?)</title>", raw)
        source_name = strip_tags(src.group(1)) if src else url
        for item in items[:limit]:
            t = re.search(r"<title>(.*?)</title>", item, re.S)
            l = re.search(r"<link>(.*?)</link>", item, re.S)
            d = re.search(r"<description>(.*?)</description>", item, re.S)
            p = re.search(r"<pubDate>(.*?)</pubDate>", item, re.S)
            title   = strip_tags(t.group(1)) if t else ""
            link    = strip_tags(l.group(1)) if l else ""
            snippet = strip_tags(d.group(1))[:500] if d else ""
            pub     = strip_tags(p.group(1)) if p else "recent"
            if any(kw in (title + snippet).lower() for kw in CYBERCRIME_KEYWORDS):
                articles.append({
                    "title": title, "snippet": snippet,
                    "url": link, "published": pub, "source": source_name
                })
    except Exception:
        pass
    return articles


def ask_gemini(query, articles, lang):
    if not GEMINI_KEY:
        return {"error": "GEMINI_API_KEY not set", "cases": [], "total_found": 0}
    if not articles:
        return {
            "cases": [], "total_found": 0,
            "search_note": "No cybercrime articles found in current RSS feeds.",
            "message": "No relevant cases found. Check https://www.nccia.gov.pk directly."
        }
    articles_text = "\n\n---\n\n".join(
        f"SOURCE: {a['source']}\nDATE: {a['published']}\nTITLE: {a['title']}\nURL: {a['url']}\nSNIPPET: {a['snippet']}"
        for a in articles
    )
    lang_note = (
        "Respond in Roman Urdu (Urdu in English letters)."
        if lang == "ur" else "Respond in English."
    )
    prompt = f"""You are a verified case extraction engine for TITAN, a Pakistani cybercrime victim support tool.

STRICT RULES:
1. Extract ONLY from the article text below. Do NOT use training data. Do NOT invent facts.
2. If a detail is missing, write: "not specified in source"
3. {lang_note}
4. Only include cases relevant to: "{query}"
5. Respond ONLY with raw JSON, no markdown, no extra text:

{{
  "cases": [
    {{
      "title": "case title",
      "date": "date or recent",
      "location": "city/province or Pakistan",
      "category": "Financial Fraud | Harassment/Blackmail | Account Hacking | SIM Fraud | Fake Officer/Digital Arrest | Fake Profile | Other",
      "peca_sections": "sections or not specified in source",
      "summary": "2-3 sentence factual summary",
      "outcome": "arrests/FIRs or outcome not yet reported",
      "source_name": "publication name",
      "source_url": "full URL"
    }}
  ],
  "total_found": 0,
  "search_note": "one sentence about sources checked"
}}

ARTICLES:
{articles_text}
"""
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048}
    }).encode("utf-8")
    req = urllib.request.Request(
        GEMINI_URL.format(key=GEMINI_KEY),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    clean = re.sub(r"```json|```", "", raw).strip()
    return json.loads(clean)


def handler(request, response):
    """Vercel Python handler format"""
    try:
        parsed = urlparse(request.url if hasattr(request, 'url') else "/")
        params = parse_qs(parsed.query)
        query = params.get("q", [""])[0].strip()
        lang  = params.get("lang", ["en"])[0]

        if not query:
            return response.json({"error": "Missing ?q= parameter"}, status=400)

        all_articles = []
        seen = set()
        for url in NEWS_SOURCES:
            for a in fetch_rss(url):
                if a["url"] not in seen:
                    seen.add(a["url"])
                    all_articles.append(a)

        q_words = query.lower().split()
        relevant = [
            a for a in all_articles
            if any(w in (a["title"] + a["snippet"]).lower() for w in q_words)
        ] or all_articles

        result = ask_gemini(query, relevant[:14], lang)
        result["query"] = query

        return response.json(result)
    except Exception as e:
        return response.json({"error": str(e), "cases": [], "total_found": 0})
