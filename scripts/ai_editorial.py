"""
Liria Research — Autonomous Editorial Engine v2
Runs every day. Never runs out of content.
- Initiates new tickers (full deep-dive)
- Publishes watchlist notes + thesis updates on existing coverage
- Always finds something worth publishing
"""
import os, json, re, sys
from datetime import datetime, timedelta
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
    os.makedirs(os.path.dirname(os.path.join(BASE, path)), exist_ok=True)
    with open(os.path.join(BASE, path), "w") as f:
        json.dump(data, f, indent=2)

def ask(prompt, model="claude-opus-4-5", max_tokens=4000):
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text.strip()

# ── Full stock universe ──────────────────────────────────────────────────────
UNIVERSE = {
    # Conviction Longs
    "MELI": {"name": "MercadoLibre",        "country": "Argentina/Brazil", "pillar": "em",  "sector": "E-Commerce / Fintech"},
    "NU":   {"name": "Nu Holdings",         "country": "Brazil",           "pillar": "em",  "sector": "Digital Banking"},
    # Emerging Markets
    "IBN":  {"name": "ICICI Bank",          "country": "India",            "pillar": "em",  "sector": "Banking"},
    "GGAL": {"name": "Grupo Galicia",       "country": "Argentina",        "pillar": "em",  "sector": "Banking"},
    "KSPI": {"name": "Kaspi.kz",            "country": "Kazakhstan",       "pillar": "em",  "sector": "Fintech / Super App"},
    "SSNLF":{"name": "Samsung Electronics", "country": "South Korea",      "pillar": "em",  "sector": "Technology"},
    "GRAB": {"name": "Grab Holdings",       "country": "Southeast Asia",   "pillar": "em",  "sector": "Super App / Fintech"},
    "SE":   {"name": "Sea Limited",         "country": "Southeast Asia",   "pillar": "em",  "sector": "Gaming / E-Commerce / Fintech"},
    "STNE": {"name": "StoneCo",             "country": "Brazil",           "pillar": "em",  "sector": "Payments / Fintech"},
    "GLOB": {"name": "Globant",             "country": "Argentina",        "pillar": "em",  "sector": "Technology / IT Services"},
    "RJHI": {"name": "Al Rajhi Bank",       "country": "Saudi Arabia",     "pillar": "em",  "sector": "Islamic Banking"},
    # Futurist Bets
    "RKLB": {"name": "Rocket Lab",          "country": "USA",              "pillar": "fut", "sector": "Space / Launch"},
    "ASTS": {"name": "AST SpaceMobile",     "country": "USA",              "pillar": "fut", "sector": "Space / Connectivity"},
    "LUNR": {"name": "Intuitive Machines",  "country": "USA",              "pillar": "fut", "sector": "Lunar / Space"},
    "OKLO": {"name": "Oklo Inc.",           "country": "USA",              "pillar": "fut", "sector": "Nuclear Energy"},
    "IONQ": {"name": "IonQ",               "country": "USA",              "pillar": "fut", "sector": "Quantum Computing"},
    "JOBY": {"name": "Joby Aviation",       "country": "USA",              "pillar": "fut", "sector": "eVTOL / Urban Air Mobility"},
    "RDW":  {"name": "Redwire",             "country": "USA",              "pillar": "fut", "sector": "Space Infrastructure"},
}

# ── Load data ────────────────────────────────────────────────────────────────
quotes         = load("data/quotes.json").get("quotes", {})
news           = load("data/news.json").get("items", [])
pub_data       = load("data/published.json")
today          = datetime.utcnow()   # naive UTC — avoids tz-aware/naive comparison errors
today_str      = today.strftime("%B %d, %Y")
date_slug      = today.strftime("%Y-%m-%d")

published_tickers = pub_data.get("tickers", [])
publication_log   = pub_data.get("log", [])

# Track last publication date per ticker (any type)
last_pub_date = {}
for entry in publication_log:
    t = entry.get("ticker")
    for fmt in ("%B %d, %Y", "%B %d %Y", "%Y-%m-%d", "%B %d, %Y"):
        try:
            d = datetime.strptime(entry.get("date", ""), fmt)
            if t not in last_pub_date or d > last_pub_date[t]:
                last_pub_date[t] = d
            break
        except:
            continue

print(f"Editorial engine v2 — {today_str}")
print(f"Universe: {len(UNIVERSE)} stocks | Initiated: {published_tickers}")

# ── Categorise candidates ────────────────────────────────────────────────────
uninitiated = [t for t in UNIVERSE if t not in published_tickers]
updateable  = [
    t for t in UNIVERSE
    if t not in last_pub_date or (today - last_pub_date[t]).days >= 14
]

print(f"Uninitiated: {uninitiated}")
print(f"Updateable (14+ days):  {updateable}")

# ── Build market brief ───────────────────────────────────────────────────────
price_lines = []
for sym in UNIVERSE:
    q = quotes.get(sym, {})
    if q:
        price_lines.append(
            f"{sym} ({UNIVERSE[sym]['name']}): ${q.get('price',0):.2f} "
            f"({q.get('changePercent',0):+.1f}% today)"
        )

news_by_ticker = {}
for item in news:
    t = item.get("ticker", "")
    news_by_ticker.setdefault(t, []).append(item["headline"])

# ── Editorial decision ───────────────────────────────────────────────────────
decision_prompt = f"""You are the editorial director of Liria Research, an independent equity research firm.

Today is {today_str}.

COVERAGE UNIVERSE ({len(UNIVERSE)} stocks):
{json.dumps({k: v for k, v in UNIVERSE.items()}, indent=2)}

UNINITIATED (eligible for full initiation or watchlist note):
{uninitiated}

UPDATEABLE (last coverage 14+ days ago — eligible for thesis update or note):
{updateable}

CURRENT PRICES:
{chr(10).join(price_lines)}

RECENT NEWS BY TICKER:
{json.dumps({k: v[:3] for k, v in news_by_ticker.items() if k in UNIVERSE}, indent=2)}

DECISION RULES — pick ONE action:
1. "initiation" — new full 2200-word deep dive on an uninitiated ticker with timely catalyst
2. "update" — 900-1100 word thesis update on any ticker with significant news/price action
3. "watchlist_note" — 450-600 word analytical note on any ticker (especially uninitiated ones)
4. "none" — ONLY if literally every single ticker was covered within the past 7 days

You MUST publish something today unless "none" is truly warranted.
Priority: initiation > conviction long update (MELI/NU) > watchlist note on uninitiated > update on any name.

Respond ONLY in valid JSON:
{{
  "decision": "initiation" | "update" | "watchlist_note" | "none",
  "ticker": "SYMBOL or null",
  "reasoning": "2-3 sentences — specific catalyst or angle",
  "title": "sharp, specific publication title",
  "angle": "the analytical edge — what does Liria see that consensus misses?",
  "rating": "Conviction Long" | "Bullish · On Watch" | "Cautious" | "High Risk · Futurist Bet" | "Neutral · Monitoring",
  "price_target": number or null,
  "word_count_target": 2200
}}"""

print("\nStep 1: Making editorial decision...")
raw = ask(decision_prompt, max_tokens=700)
raw = re.sub(r'^```(?:json)?\s*', '', raw)
raw = re.sub(r'\s*```$', '', raw)
decision = json.loads(raw)

print(f"Decision: {decision['decision']} — {decision.get('ticker')}")
print(f"Angle:    {decision.get('angle', '')}")

save("data/editorial_decision.json", {**decision, "date": today_str})

if decision["decision"] == "none":
    print("No publication needed today — all tickers recently covered.")
    sys.exit(0)

ticker   = decision["ticker"]
meta     = UNIVERSE.get(ticker, {"name": ticker, "pillar": "em", "sector": "Unknown", "country": "Unknown"})
q        = quotes.get(ticker, {})
price    = q.get("price", 0)
ticker_news = news_by_ticker.get(ticker, [])
wc_target   = decision.get("word_count_target", 2000)
is_em        = meta["pillar"] == "em"
accent_color = "var(--grn)" if is_em else "var(--pur)"
accent_rgba  = "rgba(74,222,128,0.35)" if is_em else "rgba(167,139,250,0.35)"
accent_bg    = "rgba(74,222,128,0.06)" if is_em else "rgba(167,139,250,0.06)"
pillar_label = "Emerging Markets" if is_em else "Futurist Bets"

pub_type_map   = {"initiation": "Initiation", "update": "Update", "watchlist_note": "Watchlist Note"}
pub_type_label = pub_type_map.get(decision["decision"], "Note")

prev_pubs = [e for e in publication_log if e.get("ticker") == ticker]
prev_context = ""
if prev_pubs:
    prev_context = "Previous coverage:\n" + "\n".join(
        f"  - {e['date']}: {e['title']} ({e.get('rating','')})" for e in prev_pubs
    )

# ── Generate publication HTML ────────────────────────────────────────────────
pub_prompt = f"""You are the lead analyst at Liria Research writing a formal equity research publication.

Company: {meta['name']} ({ticker})
Country:  {meta['country']}
Sector:   {meta['sector']}
Pillar:   {pillar_label}
Price:    ${price:.2f}
Target:   {decision.get('price_target') or 'No formal target'}
Rating:   {decision['rating']}
Type:     {pub_type_label}
Title:    {decision['title']}
Angle:    {decision['angle']}
Words:    ~{wc_target}
Date:     {today_str}
{prev_context}

Recent news:
{chr(10).join(f"- {h}" for h in ticker_news[:8])}

Write the complete equity research HTML below. Be rigorous, specific, honest.
Use "approximately / roughly / estimated" for uncertain figures.
Do NOT invent precise financials. Use directional analysis where needed.

Use EXACTLY this HTML skeleton (fill in all [PLACEHOLDER] sections):

<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{decision['title']} · Liria Research</title>
<link rel="stylesheet" href="../styles.css"/>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
#starfield{{position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;}}
.universe-glow{{position:fixed;width:900px;height:900px;border-radius:50%;background:radial-gradient(circle,rgba(255,255,255,0.025) 0%,transparent 70%);top:40%;left:50%;transform:translate(-50%,-50%);pointer-events:none;z-index:0;animation:breathe 8s ease-in-out infinite;}}
@keyframes breathe{{0%,100%{{opacity:.6;transform:translate(-50%,-50%) scale(1)}}50%{{opacity:1;transform:translate(-50%,-50%) scale(1.18)}}}}
#cursor{{position:fixed;width:6px;height:6px;background:#fff;border-radius:50%;pointer-events:none;z-index:9999;transform:translate(-50%,-50%);mix-blend-mode:difference;}}
#cursor-ring{{position:fixed;width:32px;height:32px;border:1px solid rgba(255,255,255,0.5);border-radius:50%;pointer-events:none;z-index:9998;transform:translate(-50%,-50%);}}
.pub-wrap{{position:relative;z-index:1;max-width:800px;margin:0 auto;padding:80px 64px 100px;}}
.pub-back{{display:inline-flex;align-items:center;gap:8px;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:rgba(255,255,255,0.35);text-decoration:none;margin-bottom:48px;transition:color .15s;}}
.pub-back:hover{{color:rgba(255,255,255,0.7);}}
.pub-eyebrow{{font-size:9px;letter-spacing:.22em;text-transform:uppercase;color:{accent_color};margin-bottom:16px;display:flex;align-items:center;gap:10px;}}
.pub-eyebrow::before{{content:'';display:block;width:3px;height:14px;background:{accent_color};flex-shrink:0;}}
.pub-h1{{font-family:var(--font-ui);font-size:clamp(28px,4vw,44px);font-weight:300;line-height:1.1;letter-spacing:-.04em;color:var(--t1);margin-bottom:24px;max-width:640px;}}
.pub-h1 em{{font-family:var(--font-serif);font-style:italic;color:{accent_color};}}
.pub-meta-row{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:48px;padding-bottom:32px;border-bottom:1px solid var(--border);}}
.pub-badge{{font-size:8.5px;letter-spacing:.14em;text-transform:uppercase;padding:5px 12px;border-radius:100px;border:1px solid {accent_rgba};color:{accent_color};background:{accent_bg};}}
.pub-ticker-tag{{font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--t4);}}
.pub-date-tag{{font-size:9px;color:var(--t4);margin-left:auto;}}
.byline{{font-size:11px;color:var(--t4);letter-spacing:.06em;margin-bottom:32px;}}
.byline strong{{color:rgba(255,255,255,0.5);}}
.lede{{font-size:16px;line-height:1.9;color:var(--t2);margin-bottom:18px;font-weight:300;}}
.lede strong{{font-weight:500;color:var(--t1);}}
.callout{{font-family:var(--font-serif);font-size:18px;line-height:1.85;color:var(--t2);margin:32px 0;padding-left:20px;border-left:3px solid {accent_color};font-style:italic;}}
.sec{{margin-top:52px;}}
.sec-label{{font-size:9px;letter-spacing:.22em;text-transform:uppercase;color:{accent_color};margin-bottom:6px;}}
.sec-title{{font-family:var(--font-ui);font-size:20px;font-weight:300;color:var(--t1);margin-bottom:18px;padding-bottom:10px;border-bottom:1px solid var(--border);letter-spacing:-.02em;}}
p{{color:var(--t2);margin-bottom:14px;font-weight:300;font-size:14.5px;line-height:1.8;}}
p strong{{color:var(--t1);font-weight:500;}}
.metric-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--border);border:1px solid var(--border);margin:24px 0;}}
.metric-cell{{background:rgba(255,255,255,0.02);padding:20px 16px;}}
.metric-label{{font-size:8px;letter-spacing:.16em;text-transform:uppercase;color:var(--t4);margin-bottom:8px;}}
.metric-value{{font-family:var(--font-serif);font-size:30px;font-weight:400;line-height:1;margin-bottom:4px;color:var(--t1);}}
.metric-note{{font-size:10px;color:var(--t3);}}
.metric-value.g{{color:var(--grn);}}
.metric-value.p{{color:var(--pur);}}
.data-table{{width:100%;border-collapse:collapse;margin:20px 0;font-size:12.5px;}}
.data-table thead th{{color:var(--t4);font-size:9px;letter-spacing:.12em;text-transform:uppercase;padding:10px 14px;text-align:left;font-weight:400;border-bottom:1px solid var(--border-med);background:rgba(255,255,255,0.02);}}
.data-table thead th:not(:first-child){{text-align:right;}}
.data-table tbody td{{padding:10px 14px;border-bottom:1px solid var(--border);color:var(--t2);font-weight:300;}}
.data-table tbody td:not(:first-child){{text-align:right;}}
.data-table tbody tr:last-child td{{border-bottom:none;}}
.tg{{color:var(--grn);font-weight:500;}}
.tp{{color:var(--pur);font-weight:500;}}
.risk-list{{list-style:none;margin:16px 0;}}
.risk-list li{{display:flex;gap:14px;align-items:flex-start;padding:18px 0;border-bottom:1px solid var(--border);}}
.risk-list li:last-child{{border-bottom:none;}}
.risk-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0;margin-top:7px;}}
.risk-dot.h{{background:#e05c5c;}}
.risk-dot.m{{background:#d4923a;}}
.risk-dot.l{{background:var(--grn);}}
.risk-title{{color:var(--t1);font-size:13.5px;font-weight:400;margin-bottom:6px;display:block;}}
.risk-body{{color:var(--t3);font-size:13px;line-height:1.75;font-weight:300;}}
.verdict-box{{margin-top:48px;border:1px solid var(--border-med);border-left:3px solid {accent_color};padding:28px 32px;background:rgba(255,255,255,0.02);}}
.verdict-label{{font-size:9px;letter-spacing:.22em;text-transform:uppercase;color:{accent_color};margin-bottom:10px;}}
.verdict-rating{{font-family:var(--font-ui);font-size:20px;font-weight:300;color:var(--t1);margin-bottom:14px;letter-spacing:-.02em;}}
.verdict-body{{font-size:13.5px;color:var(--t2);line-height:1.85;font-weight:300;}}
.pub-footer-bar{{border-top:1px solid var(--border);padding:24px 64px;font-size:10px;color:var(--t4);line-height:1.65;letter-spacing:.02em;margin-top:80px;}}
@media(max-width:640px){{
  .pub-wrap{{padding:48px 24px 80px;}}
  .pub-footer-bar{{padding:20px 24px;}}
  .metric-grid{{grid-template-columns:1fr 1fr;}}
}}
</style>
</head>
<body>
<canvas id="starfield"></canvas>
<div class="universe-glow"></div>
<div id="cursor"></div>
<div id="cursor-ring"></div>
<nav>
  <div><div class="nb-n"><span class="L">LIRIA</span><span class="R"> RESEARCH</span></div><div class="nb-s">Emerging Markets · Futurist Bets</div></div>
  <ul class="nav-links">
    <li><a href="../">Home</a></li>
    <li><a href="../publications/" class="nav-active">Publications</a></li>
    <li><a href="../watchlist/">Watchlist</a></li>
    <li><a href="../notes/">Notes</a></li>
    <li><a href="../about/">About</a></li>
  </ul>
  <div class="npill">April 2026</div>
</nav>
<div class="pub-wrap" style="padding-top:80px;">
  <a href="../publications/" class="pub-back">← Back to Publications</a>
  <div class="pub-eyebrow">{pillar_label} · {pub_type_label}</div>
  <div class="pub-h1">[WRITE THE TITLE HERE — use &lt;em&gt; tags for the key italic hook]</div>
  <div class="pub-meta-row">
    <span class="pub-badge">[RATING]</span>
    <span class="pub-ticker-tag">{ticker} · [EXCHANGE]{f"  ·  PT ${decision.get('price_target')}" if decision.get('price_target') else ""}</span>
    <span class="pub-date-tag">{today_str}</span>
  </div>
  <div class="byline">Published by <strong>LIRIA RESEARCH</strong> · Independent Equity Research</div>

  [WRITE 2-3 LEDE PARAGRAPHS — use class="lede", establish the thesis immediately]

  [WRITE ONE CALLOUT — use class="callout", the sharpest contrarian insight]

  [WRITE 4-6 SECTIONS — each uses div.sec > div.sec-label + div.sec-title + paragraphs]
  [Include metric-grid where relevant, data-table for comparisons, be analytical]

  [WRITE RISK SECTION — ul.risk-list with li items: risk-dot h/m/l + span.risk-title + p.risk-body]

  [WRITE VERDICT BOX — div.verdict-box > div.verdict-label + div.verdict-rating + div.verdict-body]
</div>
<div class="pub-footer-bar">
  Liria Research · Independent equity research · For informational purposes only · Not investment advice · {today_str}
</div>
<script>
(function(){{
  var cvs=document.getElementById('starfield'),ctx=cvs.getContext('2d'),W,H,stars=[],f=0;
  function resize(){{W=cvs.width=window.innerWidth;H=cvs.height=window.innerHeight;}}
  resize();window.addEventListener('resize',resize,{{passive:true}});
  for(var i=0;i<280;i++)stars.push({{x:Math.random()*W,y:Math.random()*H,r:Math.random()*0.7+0.1,op:Math.random()*0.4+0.05,tw:Math.random()*0.005+0.001,ph:Math.random()*Math.PI*2}});
  (function draw(){{
    ctx.clearRect(0,0,W,H);f++;
    stars.forEach(function(s){{var o=s.op+Math.sin(s.ph+f*s.tw)*0.07;ctx.beginPath();ctx.arc(s.x,s.y,s.r,0,Math.PI*2);ctx.fillStyle='rgba(255,255,255,'+Math.max(0,o)+')';ctx.fill();}});
    requestAnimationFrame(draw);
  }})();
}})();
(function(){{
  var dot=document.getElementById('cursor'),ring=document.getElementById('cursor-ring');
  if(!dot)return;
  var mx=0,my=0,rx=0,ry=0;
  document.addEventListener('mousemove',function(e){{mx=e.clientX;my=e.clientY;dot.style.left=mx+'px';dot.style.top=my+'px';}});
  (function a(){{rx+=(mx-rx)*0.12;ry+=(my-ry)*0.12;ring.style.left=rx+'px';ring.style.top=ry+'px';requestAnimationFrame(a);}})();
}})();
</script>
</body>
</html>

IMPORTANT: Return ONLY the complete HTML. No markdown. No explanations. ~{wc_target} words of analytical content."""

print(f"\nStep 2: Writing {pub_type_label} for {ticker} (~{wc_target} words)...")
pub_html = ask(pub_prompt, max_tokens=9000)
pub_html = re.sub(r'^```(?:html)?\s*', '', pub_html)
pub_html = re.sub(r'\s*```$', '', pub_html)

# ── Determine slug ───────────────────────────────────────────────────────────
if decision["decision"] == "initiation":
    base_slug = f"{ticker.lower()}-initiation"
elif decision["decision"] == "update":
    base_slug = f"{ticker.lower()}-update-{date_slug}"
else:
    base_slug = f"{ticker.lower()}-note-{date_slug}"

pub_path = os.path.join(BASE, "publications", f"{base_slug}.html")
with open(pub_path, "w") as f:
    f.write(pub_html)
print(f"✓ Saved: publications/{base_slug}.html")

# ── Update publications index ────────────────────────────────────────────────
print("\nStep 3: Updating publications index...")
desc_prompt = f"""One-sentence description (max 180 chars) for a Liria Research {pub_type_label.lower()} on {meta['name']} ({ticker}).
Title: {decision['title']}
Rating: {decision['rating']}
Angle: {decision['angle']}
Return ONLY the sentence, no quotes."""
desc = ask(desc_prompt, model="claude-haiku-4-5", max_tokens=200)

new_entry = f"""  {{
    date: '{today_str}',
    ticker: '{ticker}',
    pillar: '{meta["pillar"]}',
    type: '{pub_type_label}',
    title: '{decision["title"].replace(chr(39), chr(92)+chr(39))}',
    desc: '{desc.strip().replace(chr(39), chr(92)+chr(39))}',
    url: '/publications/{base_slug}'
  }},"""

pub_index_path = os.path.join(BASE, "publications", "index.html")
with open(pub_index_path, "r") as f:
    pub_index = f.read()

pub_index = pub_index.replace("const PUBS = [", f"const PUBS = [\n{new_entry}")
with open(pub_index_path, "w") as f:
    f.write(pub_index)
print("✓ Publications index updated")

# ── Update published.json ────────────────────────────────────────────────────
if decision["decision"] == "initiation" and ticker not in published_tickers:
    published_tickers.append(ticker)

save("data/published.json", {
    "tickers": published_tickers,
    "log": publication_log + [{
        "ticker":  ticker,
        "type":    decision["decision"],
        "title":   decision["title"],
        "date":    today_str,
        "slug":    base_slug,
        "rating":  decision["rating"],
        "pt":      decision.get("price_target")
    }]
})

print(f"\n✅ PUBLISHED: {decision['title']}")
print(f"   URL:    /publications/{base_slug}")
print(f"   Type:   {pub_type_label} | Rating: {decision['rating']}")
print(f"   Target: {decision.get('price_target', 'N/A')}")
