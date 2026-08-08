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

  // Extract Prompt & Image
  let query = req.query.q || "Analyze this request";
  let image = null;
  let mimeType = null;

  if (req.method === 'POST' && req.body) {
    query = req.body.prompt || query;
    image = req.body.image || null;
    mimeType = req.body.mimeType || null;
  }

  try {
    const parts = [];

    // Pehle prompt text add karein
    parts.push({ text: query });

    // Agar Image aayi hai toh inline_data format mein add karein
    if (image && mimeType) {
      parts.push({
        inline_data: {
          mime_type: mimeType,
          data: image
        }
      });
    }

    // Official Gemini 1.5 Flash Endpoint
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          contents: [
            {
              role: "user",
              parts: parts
            }
          ]
        }),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      console.error("Gemini API Error:", data);
      return res.status(response.status).json({ 
        reply: `API Error: ${data.error?.message || "Failed to analyze image."}` 
      });
    }

    const replyText = data.candidates?.[0]?.content?.parts?.[0]?.text;

    if (!replyText) {
      return res.status(200).json({ 
        reply: "Image read ho gayi hai lekin koi clear threat/text identify nahi hua. Koshish karein ke clear image ya receipt upload karein." 
      });
    }

    return res.status(200).json({ reply: replyText });

  } catch (error) {
    return res.status(500).json({ error: error.message });
  }
};
