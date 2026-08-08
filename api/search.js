module.exports = async (req, res) => {
  // CORS Headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  // Support both GET (query param) and POST (JSON body)
  let query = req.query.q || "Analyze this request";
  let image = null;
  let mimeType = null;

  if (req.method === 'POST' && req.body) {
    query = req.body.prompt || query;
    image = req.body.image || null;
    mimeType = req.body.mimeType || null;
  }

  const apiKey = process.env.GEMINI_API_KEY;

  if (!apiKey) {
    return res.status(500).json({ error: "GEMINI_API_KEY Missing" });
  }

  try {
    const parts = [{ text: query }];

    // If image data is sent from frontend
    if (image && mimeType) {
      parts.push({
        inline_data: {
          mime_type: mimeType,
          data: image
        }
      });
    }

    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          contents: [{ parts: parts }],
        }),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({ error: data });
    }

    const reply = data.candidates?.[0]?.content?.parts?.[0]?.text || "No response text found";
    return res.status(200).json({ reply });

  } catch (error) {
    return res.status(500).json({ error: error.message });
  }
};
