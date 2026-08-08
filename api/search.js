module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: "GEMINI_API_KEY Missing" });
  }

  let query = req.query.q || "Analyze this request";
  let image = null;
  let mimeType = null;

  if (req.method === 'POST' && req.body) {
    query = req.body.prompt || query;
    image = req.body.image || null;
    mimeType = req.body.mimeType || null;
  }

  try {
    const parts = [{ text: query }];

    if (image && mimeType) {
      parts.push({
        inline_data: {
          mime_type: mimeType,
          data: image
        }
      });
    }

    // Google ke active endpoint gemini-2.5-flash ko route kiya gaya hai
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          contents: [{ parts: parts }]
        }),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({ 
        reply: `API Error: ${data.error?.message || "Failed to analyze image."}` 
      });
    }

    const replyText = data.candidates?.[0]?.content?.parts?.[0]?.text;

    if (!replyText) {
      return res.status(200).json({ 
        reply: "Image receive ho gayi hai lekin details generate nahi ho sakti." 
      });
    }

    return res.status(200).json({ reply: replyText });

  } catch (error) {
    return res.status(500).json({ error: error.message });
  }
};
