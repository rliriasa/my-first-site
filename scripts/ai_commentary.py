"""
Liria Research — AI daily commentary generator
Reads quotes.json + news.json, calls Claude API, writes data/commentary.json
Runs via GitHub Actions after refresh_data.py
"""
import os, json, re
from datetime import datetime, timezone
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load(path):
    try:
        with open(os.path.join(BASE, path)) as f:
            return json.load(f)
    except Exception:
        return {}

quotes_data = load("data/quotes.json")
news_data   = load("data/news.json")

quotes = quotes_data.get("quotes", {})
news   = news_data.get("items", [])

COVERAGE = {
    "MELI":  {"name": "MercadoLibre",          "type": "conviction", "pt": 2400},
    "NU":    {"name": "Nu Holdings",            "type": "conviction", "pt": 18},
    "IBN":   {"name": "ICICI Bank",             "type": "watch",      "pt": None},
    "SSNLF": {"name": "Samsung Electronics",    "type": "watch",      "pt": None},
    "GGAL":  {"name": "Grupo Galicia",          "type": "watch",      "pt": None},
    "RJHI":  {"name": "Al Rajhi Bank",          "type": "watch",      "pt": None},
    "ASTS":  {"name": "AST SpaceMobile",        "type": "watch",      "pt": None},
    "RKLB":  {"name": "Rocket Lab",             "type": "watch",      "pt": None},
    "OKLO":  {"name": "Oklo Inc.",              "type": "watch",      "pt": None},
    "LUNR":  {"name": "Intuitive Machines",     "type": "watch",      "pt": None},
}

# ── Build context for Claude ─────────────────────────────────────────────────
price_lines = []
for sym, meta in COVERAGE.items():
    q = quotes.get(sym, {})
    if not q:
        continue
    price = q.get("price", 0)
    chg   = q.get("changePercent", 0)
    line  = f"{sym} ({meta['name']}): ${price} ({chg:+.1f}%)"
    if meta["pt"]:
        upside = ((meta["pt"] - price) / price * 100) if price else 0
        line  += f" | PT ${meta['pt']} | {upside:+.1f}% to target"
    price_lines.append(line)

recent_news = []
for item in news[:15]:
    recent_news.append(f"[{item['ticker']}] {item['headline']} ({item.get('tagLabel','Neutral')})")

today_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

prompt = f"""You are the analyst behind Liria Research — an independent equity research firm covering 10 names across Emerging Markets and frontier technology.

Today is {today_str}.

Current prices:
{chr(10).join(price_lines)}

Recent news headlines:
{chr(10).join(recent_news)}

Write a concise daily research note in JSON format with these fields:
- "date": today's date string
- "headline": a sharp 1-line market observation (10 words max, no fluff)
- "conviction_update": 2-3 sentences on MELI and NU specifically — price action, news, thesis status. Be specific and analytical, not generic.
- "watchlist_movers": list of up to 3 objects with "sym", "note" (1 sharp sentence on what's notable today, if anything — skip if nothing meaningful)
- "market_context": 1 sentence on the broader EM or frontier tech backdrop relevant to our coverage
- "thesis_intact": true/false for each conviction name — object with "MELI" and "NU" keys

Tone: institutional, sharp, no filler. Think Goldman morning note meets independent research.

Return only valid JSON, no markdown.
"""

print("Calling Claude API…")
msg = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=800,
    messages=[{"role": "user", "content": prompt}]
)

raw = msg.content[0].text.strip()

# Strip markdown code fences if present
raw = re.sub(r'^```(?:json)?\s*', '', raw)
raw = re.sub(r'\s*```$', '', raw)

try:
    commentary = json.loads(raw)
    commentary["generated_at"] = datetime.now(timezone.utc).isoformat()

    out_path = os.path.join(BASE, "data", "commentary.json")
    with open(out_path, "w") as f:
        json.dump(commentary, f, indent=2)
    print(f"✓ Commentary saved to data/commentary.json")
    print(f"  Headline: {commentary.get('headline')}")
except json.JSONDecodeError as e:
    print(f"⚠ JSON parse error: {e}")
    print("Raw response:", raw[:300])
    # Save raw anyway so we don't lose it
    with open(os.path.join(BASE, "data", "commentary_raw.txt"), "w") as f:
        f.write(raw)
