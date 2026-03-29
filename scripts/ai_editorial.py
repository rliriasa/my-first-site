"""
Liria Research — Autonomous Editorial Engine
Runs every Monday. Decides what to publish, generates full research reports,
updates the website. No human input required.
"""
import os, json, re, sys
from datetime import datetime, timezone
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load(path):
    try:
        with open(os.path.join(BASE, path)) as f:
            return json.load(f)
    except:
        return {}

def save(path, data):
    with open(os.path.join(BASE, path), "w") as f:
        json.dump(data, f, indent=2)

def ask(prompt, model="claude-opus-4-5", max_tokens=4000):
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text.strip()

# ── Load all available data ──────────────────────────────────────────────────
quotes   = load("data/quotes.json").get("quotes", {})
news     = load("data/news.json").get("items", [])
already  = load("data/published.json")  # tracks what's been published

WATCHLIST = {
    "IBN":   {"name": "ICICI Bank",          "country": "India",        "pillar": "em",  "sector": "Banking"},
    "SSNLF": {"name": "Samsung Electronics", "country": "South Korea",  "pillar": "em",  "sector": "Technology"},
    "GGAL":  {"name": "Grupo Galicia",        "country": "Argentina",    "pillar": "em",  "sector": "Banking"},
    "RJHI":  {"name": "Al Rajhi Bank",        "country": "Saudi Arabia", "pillar": "em",  "sector": "Banking"},
    "KSPI":  {"name": "Kaspi.kz",             "country": "Kazakhstan",   "pillar": "em",  "sector": "Fintech / Super App"},
    "ASTS":  {"name": "AST SpaceMobile",      "country": "USA",          "pillar": "fut", "sector": "Space Tech"},
    "RKLB":  {"name": "Rocket Lab",           "country": "USA",          "pillar": "fut", "sector": "Space Tech"},
    "OKLO":  {"name": "Oklo Inc.",            "country": "USA",          "pillar": "fut", "sector": "Nuclear Energy"},
    "LUNR":  {"name": "Intuitive Machines",   "country": "USA",          "pillar": "fut", "sector": "Space Tech"},
}

published_tickers = already.get("tickers", [])
candidates = {k: v for k, v in WATCHLIST.items() if k not in published_tickers}

today = datetime.now(timezone.utc)
today_str = today.strftime("%B %d, %Y")
date_slug = today.strftime("%Y-%m-%d")

print(f"Editorial engine running — {today_str}")
print(f"Candidates: {list(candidates.keys())}")

# ── Build market brief ───────────────────────────────────────────────────────
price_lines = []
for sym, meta in WATCHLIST.items():
    q = quotes.get(sym, {})
    if q:
        price_lines.append(f"{sym}: ${q.get('price',0)} ({q.get('changePercent',0):+.1f}% today, {q.get('change52wHigh',0):+.1f}% from 52w high)")

news_by_ticker = {}
for item in news:
    t = item["ticker"]
    if t not in news_by_ticker:
        news_by_ticker[t] = []
    news_by_ticker[t].append(item["headline"])

# ── Step 1: Editorial decision ───────────────────────────────────────────────
decision_prompt = f"""You are the editorial director of Liria Research, an independent equity research firm with a track record of publishing only when there is genuine analytical edge.

Today is {today_str}. You have already published initiations on: NU Holdings, MercadoLibre.

Remaining watchlist candidates for initiation:
{json.dumps({k: v for k, v in candidates.items()}, indent=2)}

Current prices:
{chr(10).join(price_lines)}

Recent news by ticker:
{json.dumps({k: v[:3] for k, v in news_by_ticker.items() if k in candidates}, indent=2)}

Your job: decide whether to publish a new initiation this week. Only publish if:
1. There is a genuinely differentiated thesis (not just "it's a good company")
2. The price creates an interesting risk/reward
3. There is enough information to write a credible 2000+ word report
4. The story is timely (recent catalyst, earnings, macro development, or severe mispricing)

Also decide on the publication TYPE:
- "initiation": full deep dive, conviction long or short
- "update": existing position update (if major news on NU/MELI)
- "watchlist_note": short 400-word analytical note on a watchlist name
- "none": skip this week, quality over quantity

Respond in JSON:
{{
  "decision": "initiation" | "update" | "watchlist_note" | "none",
  "ticker": "SYMBOL or null",
  "reasoning": "2-3 sentences on why",
  "title": "compelling publication title if publishing",
  "angle": "the specific analytical edge / hook for this report",
  "rating": "Conviction Long" | "Bullish · On Watch" | "Cautious" | "High Risk · Futurist Bet",
  "price_target": number or null,
  "urgency": "high" | "medium" | "low"
}}

Return only valid JSON."""

print("\nStep 1: Making editorial decision...")
decision_raw = ask(decision_prompt, model="claude-opus-4-5", max_tokens=600)
decision_raw = re.sub(r'^```(?:json)?\s*', '', decision_raw)
decision_raw = re.sub(r'\s*```$', '', decision_raw)
decision = json.loads(decision_raw)

print(f"Decision: {decision['decision']} — {decision.get('ticker','none')}")
print(f"Reasoning: {decision['reasoning']}")

save("data/editorial_decision.json", {**decision, "date": today_str})

if decision["decision"] == "none":
    print("No publication this week. Editorial standard maintained.")
    sys.exit(0)

ticker = decision["ticker"]
meta   = WATCHLIST.get(ticker, {}) or {"name": ticker, "pillar": "em", "sector": "Unknown", "country": "Unknown"}

# ── Step 2: Generate full publication ────────────────────────────────────────
ticker_news = news_by_ticker.get(ticker, [])
q = quotes.get(ticker, {})
price = q.get("price", 0)

pub_prompt = f"""You are the lead analyst at Liria Research writing a formal equity research publication.

Company: {meta['name']} ({ticker})
Country: {meta['country']}
Sector: {meta['sector']}
Current Price: ${price}
Price Target: {decision.get('price_target', 'TBD')}
Rating: {decision['rating']}
Publication Type: {decision['decision']}
Title: {decision['title']}
Analytical angle: {decision['angle']}
Today: {today_str}

Recent news:
{chr(10).join(f'- {h}' for h in ticker_news[:8])}

Write a complete, rigorous equity research report in HTML using EXACTLY this structure and CSS classes.
The report must be 2000+ words, deeply analytical, with specific numbers where known and honest acknowledgment where uncertain.
Use "approximately", "estimated", "roughly" when precise figures are unavailable.
DO NOT invent specific financial figures you cannot verify. Use directional analysis where needed.

Use this EXACT HTML structure (fill in the content):

<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{decision['title']} · Liria Research</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400;1,600&family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@300;400;500&display=swap" rel="stylesheet"/>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
:root{{
  --nd:#07111f;--nm:#0d1e33;--nc:#0b1929;--nr:#101f34;
  --b1:#1a2f4a;--b2:#213858;
  --t1:#e8edf5;--t2:#adc0d6;--t3:#7a96b0;--t4:#4e6882;
  --gold:#c9a84c;--grn:#3cb87a;--red:#e05c5c;--amb:#d4923a;
}}
html{{background:var(--nd);}}
body{{font-family:'DM Sans',sans-serif;font-size:15px;line-height:1.75;color:var(--t1);background:var(--nm);max-width:800px;margin:0 auto;box-shadow:0 0 60px rgba(0,0,0,.4);}}
.pub-header{{background:var(--nd);border-bottom:1px solid var(--b1);padding:40px 64px 44px;position:relative;}}
.pub-series{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.22em;text-transform:uppercase;color:var(--t4);margin-bottom:16px;display:flex;align-items:center;gap:10px;}}
.pub-series::before{{content:'';display:block;width:3px;height:14px;background:var(--grn);flex-shrink:0;}}
.pub-title{{font-family:'Cormorant Garamond',serif;font-size:clamp(28px,4vw,42px);font-weight:700;color:var(--t1);line-height:1.1;letter-spacing:-.02em;margin-bottom:22px;max-width:580px;}}
.pub-title em{{color:var(--grn);font-style:italic;}}
.pub-meta{{display:flex;align-items:center;gap:14px;flex-wrap:wrap;}}
.pub-rating{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.14em;text-transform:uppercase;background:rgba(60,184,122,.08);border:1px solid rgba(60,184,122,.3);color:var(--grn);padding:5px 12px;}}
.pub-ticker-badge{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.14em;text-transform:uppercase;color:var(--t3);}}
.pub-date{{position:absolute;top:40px;right:64px;font-family:'DM Mono',monospace;font-size:10px;color:var(--t4);letter-spacing:.06em;}}
.pub-body{{padding:52px 64px 80px;}}
.byline{{font-family:'DM Mono',monospace;font-size:11px;color:var(--t3);letter-spacing:.06em;margin-bottom:32px;padding-bottom:20px;border-bottom:1px solid var(--b1);}}
.byline strong{{color:var(--gold);}}
.lede{{font-size:16px;line-height:1.85;color:var(--t2);margin-bottom:18px;font-weight:300;}}
.lede strong{{font-weight:500;color:var(--t1);}}
.callout{{font-family:'Cormorant Garamond',serif;font-size:17px;line-height:1.8;color:var(--t2);font-weight:400;margin:28px 0;padding-left:20px;border-left:3px solid var(--grn);}}
.section{{margin-top:56px;}}
.section-label{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.22em;text-transform:uppercase;color:var(--gold);margin-bottom:6px;}}
.section-title{{font-family:'Cormorant Garamond',serif;font-size:22px;font-weight:700;color:var(--t1);margin-bottom:20px;padding-bottom:10px;border-bottom:1px solid var(--b1);display:block;}}
p{{color:var(--t2);margin-bottom:14px;font-weight:300;}}
p strong{{color:var(--t1);font-weight:500;}}
.metric-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--b1);border:1px solid var(--b1);margin:4px 0;}}
.metric-cell{{background:var(--nc);padding:18px 16px;}}
.metric-label{{font-family:'DM Mono',monospace;font-size:8px;letter-spacing:.16em;text-transform:uppercase;color:var(--t4);margin-bottom:8px;}}
.metric-value{{font-family:'Cormorant Garamond',serif;font-size:28px;font-weight:700;line-height:1;margin-bottom:4px;color:var(--t1);}}
.metric-note{{font-size:10px;color:var(--t3);}}
.metric-value.g{{color:var(--grn);}}
.metric-value.r{{color:var(--red);}}
.metric-value.b{{color:var(--gold);}}
.data-table{{width:100%;border-collapse:collapse;margin:4px 0;font-size:12.5px;}}
.data-table thead tr{{background:var(--nd);}}
.data-table thead th{{color:var(--t3);font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.12em;text-transform:uppercase;padding:10px 14px;text-align:left;font-weight:400;border-bottom:1px solid var(--b2);}}
.data-table thead th:not(:first-child){{text-align:right;}}
.data-table tbody td{{padding:10px 14px;border-bottom:1px solid var(--b1);color:var(--t2);font-size:12.5px;font-weight:300;}}
.data-table tbody td:not(:first-child){{text-align:right;}}
.data-table tbody tr:last-child td{{border-bottom:none;}}
.data-table tbody tr:hover td{{background:var(--nr);}}
.tg{{color:var(--grn);font-weight:500;}}
.tr{{color:var(--red);font-weight:500;}}
.ta{{color:var(--amb);font-weight:500;}}
.tb{{color:var(--gold);font-weight:500;}}
.risk-list{{list-style:none;margin:16px 0;}}
.risk-list li{{display:flex;gap:14px;align-items:flex-start;padding:18px 0;border-bottom:1px solid var(--b1);color:var(--t2);}}
.risk-list li:last-child{{border-bottom:none;}}
.risk-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0;margin-top:7px;}}
.risk-dot.h{{background:var(--red);}}
.risk-dot.m{{background:var(--amb);}}
.risk-dot.l{{background:var(--grn);}}
.risk-content strong{{display:block;color:var(--t1);font-size:13.5px;font-weight:500;margin-bottom:8px;}}
.risk-content p{{font-size:13px;margin-bottom:10px;color:var(--t2);font-weight:300;line-height:1.75;}}
.verdict-box{{margin-top:48px;border:1px solid var(--b2);border-left:3px solid var(--grn);padding:28px 32px;background:var(--nc);}}
.verdict-label{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.22em;text-transform:uppercase;color:var(--grn);margin-bottom:10px;}}
.verdict-rating{{font-family:'Cormorant Garamond',serif;font-size:22px;font-weight:700;color:var(--t1);margin-bottom:14px;}}
.verdict-body{{font-size:14px;color:var(--t2);line-height:1.8;font-weight:300;}}
.verdict-body strong{{color:var(--t1);font-weight:500;}}
.pub-footer{{border-top:1px solid var(--b1);padding:24px 64px 36px;font-size:10px;color:var(--t4);line-height:1.65;font-family:'DM Mono',monospace;letter-spacing:.02em;background:var(--nd);}}
@media(max-width:640px){{
  .pub-header,.pub-body,.pub-footer{{padding-left:24px;padding-right:24px;}}
  .pub-date{{position:static;margin-bottom:16px;}}
  .metric-grid{{grid-template-columns:1fr 1fr;}}
}}
</style>
</head>
<body>
<div class="pub-header">
  <div class="pub-date">{today_str}</div>
  <div class="pub-series">[PILLAR] Coverage · [TYPE]</div>
  <div class="pub-title">[TITLE WITH <em>ITALIC HOOK</em>]</div>
  <div class="pub-meta">
    <span class="pub-rating">[RATING]</span>
    <span class="pub-ticker-badge">{ticker} · [EXCHANGE] · [PT or "On Watch"]</span>
  </div>
</div>
<div class="pub-body">
  <div class="byline">Published by <strong>LIRIA RESEARCH</strong> · Independent Equity Research</div>
  [LEDE PARAGRAPHS — 2-3 powerful opening paragraphs]
  [CALLOUT — one key insight in callout div]
  [4-6 SECTIONS with section-label, section-title, paragraphs, metric-grids, data-tables]
  [RISK SECTION with risk-list items]
  [VERDICT BOX]
</div>
<div class="pub-footer">
  Liria Research · Independent equity research · Not investment advice · All positions owned by the analyst · {today_str}
</div>
</body>
</html>

Write the complete HTML. Be specific, analytical, and honest. Cite approximate figures, use ranges where exact data unavailable. The goal is genuine analytical value, not marketing. Return only the HTML."""

print(f"\nStep 2: Generating full publication for {ticker}...")
pub_html = ask(pub_prompt, model="claude-opus-4-5", max_tokens=8000)

# Clean up any markdown wrapping
pub_html = re.sub(r'^```(?:html)?\s*', '', pub_html)
pub_html = re.sub(r'\s*```$', '', pub_html)

# Save the publication
slug = f"{ticker.lower()}-initiation"
pub_path = os.path.join(BASE, "publications", f"{slug}.html")
with open(pub_path, "w") as f:
    f.write(pub_html)
print(f"✓ Publication saved: publications/{slug}.html")

# ── Step 3: Update publications/index.html PUBS array ───────────────────────
print("\nStep 3: Updating publications index...")

# Generate a one-line description
desc_prompt = f"""Write a 1-sentence description (max 180 chars) for a research publication on {meta['name']} ({ticker}).
Title: {decision['title']}
Rating: {decision['rating']}
Price target: {decision.get('price_target','N/A')}
Current price: ${price}
Angle: {decision['angle']}
Return only the sentence, no quotes."""

desc = ask(desc_prompt, model="claude-haiku-4-5", max_tokens=200)

new_entry = f"""  {{
    date: '{today_str}',
    ticker: '{ticker}',
    pillar: '{meta["pillar"]}',
    type: '{decision["decision"].title()}',
    title: '{decision["title"].replace("'", "\\'")}',
    desc: '{desc.strip().replace(chr(39), chr(92)+chr(39))}',
    url: '/publications/{slug}'
  }},"""

pub_index_path = os.path.join(BASE, "publications", "index.html")
with open(pub_index_path, "r") as f:
    pub_index = f.read()

# Insert at top of PUBS array
pub_index = pub_index.replace("const PUBS = [", f"const PUBS = [\n{new_entry}")
with open(pub_index_path, "w") as f:
    f.write(pub_index)
print("✓ Publications index updated")

# ── Step 4: Track what we've published ───────────────────────────────────────
published_tickers.append(ticker)
save("data/published.json", {
    "tickers": published_tickers,
    "log": already.get("log", []) + [{
        "ticker": ticker,
        "title": decision["title"],
        "date": today_str,
        "slug": slug,
        "rating": decision["rating"],
        "pt": decision.get("price_target")
    }]
})

print(f"\n🟢 PUBLISHED: {decision['title']}")
print(f"   URL: /publications/{slug}")
print(f"   Rating: {decision['rating']}")
print(f"   PT: {decision.get('price_target','N/A')}")
