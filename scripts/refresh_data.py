"""
Liria Investments — daily market data refresh
Fetches quotes and news from Finnhub, writes to data/quotes.json and data/news.json.
Runs via GitHub Actions. Requires FINNHUB_API_KEY environment variable.
"""
import os, json, time, requests
from datetime import datetime, timezone, timedelta

API_KEY = os.environ.get('FINNHUB_API_KEY', '')
BASE    = 'https://finnhub.io/api/v1'

TICKERS = {
    # Emerging Markets
    'MELI':  {'name': 'MercadoLibre',          'pillar': 'em'},
    'NU':    {'name': 'Nu Holdings',            'pillar': 'em'},
    'IBN':   {'name': 'ICICI Bank',             'pillar': 'em'},
    'GGAL':  {'name': 'Grupo Fin. Galicia',     'pillar': 'em'},
    'KSPI':  {'name': 'Kaspi.kz',               'pillar': 'em'},
    'SSNLF': {'name': 'Samsung Electronics',    'pillar': 'em'},
    'GRAB':  {'name': 'Grab Holdings',          'pillar': 'em'},
    'SE':    {'name': 'Sea Limited',            'pillar': 'em'},
    'STNE':  {'name': 'StoneCo',               'pillar': 'em'},
    'GLOB':  {'name': 'Globant',               'pillar': 'em'},
    'RJHI':  {'name': 'Al Rajhi Bank',          'pillar': 'em'},
    # Futurist Bets
    'RKLB':  {'name': 'Rocket Lab',             'pillar': 'fut'},
    'ASTS':  {'name': 'AST SpaceMobile',        'pillar': 'fut'},
    'LUNR':  {'name': 'Intuitive Machines',     'pillar': 'fut'},
    'OKLO':  {'name': 'Oklo Inc.',              'pillar': 'fut'},
    'IONQ':  {'name': 'IonQ',                  'pillar': 'fut'},
    'JOBY':  {'name': 'Joby Aviation',          'pillar': 'fut'},
    'RDW':   {'name': 'Redwire',               'pillar': 'fut'},
}

BULL_KW = ['up','gain','rise','rose','beat','record','wins','award','growth','buy','bullish',
           'strong','positive','upgrade','expands','secures','launches','approves','signs']
BEAR_KW = ['down','fall','drop','miss','loss','sell','cut','weak','negative','downgrade',
           'decline','warning','risk','sheds','plunges','slides','delays','cancels']

def classify(headline, summary=''):
    text = (headline + ' ' + summary).lower()
    bull = sum(1 for k in BULL_KW if k in text)
    bear = sum(1 for k in BEAR_KW if k in text)
    if bull > bear:  return 'bull',  'Bullish'
    if bear > bull:  return 'bear',  'Bearish'
    return 'neut', 'Neutral'

def api_get(endpoint, params):
    if not API_KEY:
        return {}
    params['token'] = API_KEY
    try:
        r = requests.get(f'{BASE}{endpoint}', params=params, timeout=12)
        return r.json() if r.ok else {}
    except Exception as e:
        print(f'  ⚠ API error {endpoint}: {e}')
        return {}

# ── Load existing data as fallback ──────────────────────────────────────────
os.makedirs('data', exist_ok=True)
existing_quotes = {}
existing_news   = []
try:
    with open('data/quotes.json') as f:
        existing_quotes = json.load(f).get('quotes', {})
except Exception:
    pass
try:
    with open('data/news.json') as f:
        existing_news = json.load(f).get('items', [])
except Exception:
    pass

# ── Fetch ────────────────────────────────────────────────────────────────────
quotes     = dict(existing_quotes)   # start from existing; overwrite on success
news_items = []
today      = datetime.now(timezone.utc)
from_date  = (today - timedelta(days=7)).strftime('%Y-%m-%d')
to_date    = today.strftime('%Y-%m-%d')

for ticker, meta in TICKERS.items():
    print(f'Fetching {ticker}…')

    # Quote
    q = api_get('/quote', {'symbol': ticker})
    time.sleep(0.4)
    if q.get('c') and float(q['c']) > 0:
        quotes[ticker] = {
            'price':         round(float(q['c']),  2),
            'change':        round(float(q.get('d',  0)), 2),
            'changePercent': round(float(q.get('dp', 0)), 2),
            'high':          round(float(q.get('h',  0)), 2),
            'low':           round(float(q.get('l',  0)), 2),
            'prevClose':     round(float(q.get('pc', 0)), 2),
        }
        print(f'  ✓ ${quotes[ticker]["price"]}  {quotes[ticker]["changePercent"]:+.2f}%')
    else:
        print(f'  – no quote data (keeping existing)')

    # News (last 7 days)
    news = api_get('/company-news', {'symbol': ticker, 'from': from_date, 'to': to_date})
    time.sleep(0.4)
    if isinstance(news, list):
        for item in news[:5]:
            headline = (item.get('headline') or '').strip()
            summary  = (item.get('summary')  or '').strip()
            if not headline:
                continue
            tag, tag_label = classify(headline, summary)
            ts      = item.get('datetime', 0)
            dt      = datetime.fromtimestamp(ts, tz=timezone.utc)
            news_items.append({
                'ticker':   ticker,
                'pillar':   meta['pillar'],
                'date':     dt.strftime('%b %-d, %Y'),
                'datetime': ts,
                'tag':      tag,
                'tagLabel': tag_label,
                'headline': headline,
                'summary':  summary[:320],
                'source':   item.get('source', ''),
                'url':      item.get('url', ''),
            })
        print(f'  ✓ {len([x for x in news_items if x["ticker"]==ticker])} news items')

# ── Deduplicate & sort news ──────────────────────────────────────────────────
seen, final_news = set(), []
for item in sorted(news_items, key=lambda x: x['datetime'], reverse=True):
    key = item['headline'][:80]
    if key not in seen:
        seen.add(key)
        final_news.append(item)

# Keep existing news if Finnhub returned nothing useful
if not final_news:
    print('No new news items fetched — keeping existing data.')
    final_news = existing_news

# ── Write output ─────────────────────────────────────────────────────────────
with open('data/quotes.json', 'w') as f:
    json.dump({'updated': today.isoformat(), 'quotes': quotes}, f, indent=2)

with open('data/news.json', 'w') as f:
    json.dump({'updated': today.isoformat(), 'items': final_news[:50]}, f, indent=2)

print(f'\n✅ Done: {len(quotes)} quotes, {len(final_news)} news items written.')
