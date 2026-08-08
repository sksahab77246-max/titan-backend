const https = require('https');
const http = require('http');

const NEWS_SOURCES = [
  'https://www.dawn.com/feeds/home',
  'https://arynews.tv/feed/',
  'https://www.nation.com.pk/rss/',
  'https://propakistani.pk/feed/',
  'https://profit.pakistantoday.com.pk/feed/',
];

const KEYWORDS = [
  'nccia','cybercrime','cyber crime','peca','online fraud','digital arrest',
  'fake investment','blackmail','sim swap','phishing','hacking','online scam',
  'whatsapp fraud','crypto scam','fake profile','arrested','fraud','scam',
];

function stripTags(html) {
  return html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}

function fetchUrl(url) {
  return new Promise((resolve) => {
    const lib = url.startsWith('https') ? https : http;
    const req = lib.get(url, {
      headers: { 'User-Agent': 'TITAN-Cyber-Guardian/1.0' },
      timeout: 8000,
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data));
    });
    req.on('error', () => resolve(''));
    req.on('timeout', () => { req.destroy(); resolve(''); });
  });
}

async function fetchRSS(url) {
  const raw = await fetchUrl(url);
  if (!raw) return [];
  const articles = [];
  const srcMatch = raw.match(/<title>(.*?)<\/title>/s);
  const sourceName = srcMatch ? stripTags(srcMatch[1]) : url;
  const items = raw.match(/<item>(.*?)<\/item>/gs) || [];
  for (const item of items.slice(0, 10)) {
    const t = item.match(/<title>(.*?)<\/title>/s);
    const l = item.match(/<link>(.*?)<\/link>/s);
    const d = item.match(/<description>(.*?)<\/description>/s);
    const p = item.match(/<pubDate>(.*?)<\/pubDate>/s);
    const title   = t ? stripTags(t[1]) : '';
    const link    = l ? stripTags(l[1]) : '';
    const snippet = d ? stripTags(d[1]).slice(0, 500) : '';
    const pub     = p ? stripTags(p[1]) : 'recent';
    const blob = (title + snippet).toLowerCase();
    if (KEYWORDS.some(kw => blob.includes(kw))) {
      articles.push({ title, snippet, url: link, published: pub, source: sourceName });
    }
  }
  return articles;
}

async function askGemini(query, articles, lang) {
  const key = process.env.GEMINI_API_KEY;
  if (!key) return { error: 'GEMINI_API_KEY not set', cases: [], total_found: 0 };
  if (!articles.length) return {
    cases: [], total_found: 0,
    search_note: 'No cybercrime articles in current RSS feeds.',
    message: 'No relevant cases found. Check https://www.nccia.gov.pk directly.'
  };

  const articlesText = articles.map(a =>
    `SOURCE: ${a.source}\nDATE: ${a.published}\nTITLE: ${a.title}\nURL: ${a.url}\nSNIPPET: ${a.snippet}`
  ).join('\n\n---\n\n');

  const langNote = lang === 'ur'
    ? 'Respond in Roman Urdu (Urdu written in English letters).'
    : 'Respond in English.';

  const prompt = `You are a verified case extraction engine for TITAN, a Pakistani cybercrime victim support tool.

STRICT RULES:
1. Extract ONLY from the article text below. Do NOT use training data. Do NOT invent facts.
2. If a detail is missing write: "not specified in source"
3. ${langNote}
4. Only include cases relevant to: "${query}"
5. Respond ONLY with raw JSON, no markdown, no extra text:

{
  "cases": [
    {
      "title": "case title",
      "date": "date or recent",
      "location": "city/province or Pakistan",
      "category": "Financial Fraud | Harassment/Blackmail | Account Hacking | SIM Fraud | Fake Officer/Digital Arrest | Fake Profile | Other",
      "peca_sections": "sections or not specified in source",
      "summary": "2-3 sentence factual summary",
      "outcome": "arrests/FIRs or outcome not yet reported",
      "source_name": "publication name",
      "source_url": "full URL"
    }
  ],
  "total_found": 0,
  "search_note": "one sentence about sources checked"
}

ARTICLES:
${articlesText}`;

  const body = JSON.stringify({
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: { temperature: 0.1, maxOutputTokens: 2048 }
  });

  return new Promise((resolve) => {
    const options = {
      hostname: 'generativelanguage.googleapis.com',
      path: `/v1beta/models/gemini-1.5-flash:generateContent?key=${key}`,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) }
    };
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          const raw = parsed.candidates[0].content.parts[0].text.trim();
          const clean = raw.replace(/```json|```/g, '').trim();
          resolve(JSON.parse(clean));
        } catch(e) {
          resolve({ error: 'Gemini parse error: ' + e.message, cases: [], total_found: 0 });
        }
      });
    });
    req.on('error', (e) => resolve({ error: e.message, cases: [], total_found: 0 }));
    req.write(body);
    req.end();
  });
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') { res.status(200).end(); return; }

  const query = (req.query.q || '').trim();
  const lang  = req.query.lang || 'en';

  if (!query) {
    res.status(400).json({ error: 'Missing ?q= parameter' });
    return;
  }

  try {
    const allArticles = [];
    const seen = new Set();
    for (const url of NEWS_SOURCES) {
      const arts = await fetchRSS(url);
      for (const a of arts) {
        if (!seen.has(a.url)) { seen.add(a.url); allArticles.push(a); }
      }
    }

    const qWords = query.toLowerCase().split(' ');
    let relevant = allArticles.filter(a =>
      qWords.some(w => (a.title + a.snippet).toLowerCase().includes(w))
    );
    if (!relevant.length) relevant = allArticles;

    const result = await askGemini(query, relevant.slice(0, 14), lang);
    result.query = query;
    res.status(200).json(result);
  } catch(e) {
    res.status(500).json({ error: e.message, cases: [], total_found: 0 });
  }
};
