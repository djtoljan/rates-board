"""Fetch exchange rates from CBR, Investing.com (via curl), XFeepay. Write rates.json."""
import json, os, subprocess, sys, xml.etree.ElementTree as ET, urllib.request
from datetime import datetime, timezone

RATES_FILE = os.path.join(os.getcwd(), 'rates.json')

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')

def curl_get(url, timeout=15):
    """curl wrapper — returns stdout str or empty on error."""
    try:
        r = subprocess.run(
            ['curl', '-s', '-L', '--max-time', str(timeout),
             '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
             '-H', 'Accept: text/html,application/xhtml+xml',
             '-H', 'Accept-Language: ru-RU,ru;q=0.9',
             url],
            capture_output=True, text=True, timeout=timeout+5
        )
        return r.stdout if r.returncode == 0 else ''
    except:
        return ''

def parse_jsonld(html):
    """Extract FAQPage JSON-LD from investing.com HTML. Returns dict of {question_name: answer_text}."""
    import re
    # Find JSON-LD block
    m = re.search(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
        if data.get('@type') != 'FAQPage':
            return {}
        qa = {}
        for item in data.get('mainEntity', []):
            qname = item.get('name', '')
            atext = item.get('acceptedAnswer', {}).get('text', '')
            qa[qname] = atext
        return qa
    except:
        return {}

def parse_rate_from_qa(qa, key_prefix='Exchange Rate'):
    """Find rate in QA dict — returns float or None."""
    for q, a in qa.items():
        if key_prefix in q:
            # Extract number
            import re
            nums = re.findall(r'[\d]+\.[\d]+', a)
            if nums:
                return float(nums[0])
    return None

# Load existing data
data = {}
if os.path.exists(RATES_FILE):
    try:
        with open(RATES_FILE) as f:
            data = json.load(f)
    except:
        data = {}

# ─── 1. CBR — RUB per unit ───────────────────────────────
try:
    req = urllib.request.Request('https://www.cbr.ru/scripts/XML_daily.asp',
                                 headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        xml_text = resp.read().decode('windows-1251')
    root = ET.fromstring(xml_text)
    targets = {'USD': 'R01235', 'EUR': 'R01239', 'CNY': 'R01375', 'TRY': 'R01700J'}
    cbr = {}
    for v in root.findall('Valute'):
        vid = v.get('ID')
        for code, tid in targets.items():
            if vid == tid:
                nominal = int(v.find('Nominal').text)
                value = float(v.find('Value').text.replace(',', '.'))
                cbr[code] = round(value / nominal, 4)
    data['cbr'] = cbr
    log(f'CBR ok: {cbr}')
except Exception as e:
    log(f'CBR error: {e}')

# ─── 2. Investing.com via curl + JSON-LD (RUB-pairs) ─────
try:
    rub_pairs = {
        'USD': 'https://www.investing.com/currencies/usd-rub',
        'EUR': 'https://www.investing.com/currencies/eur-rub',
        'CNY': 'https://www.investing.com/currencies/cny-rub',
        'TRY': 'https://www.investing.com/currencies/try-rub',
    }
    investing = {}
    for code, url in rub_pairs.items():
        html = curl_get(url)
        if not html:
            log(f'  {code}: empty response')
            continue
        qa = parse_jsonld(html)
        rate = parse_rate_from_qa(qa, 'Exchange Rate')
        if rate:
            investing[code] = round(rate, 4)
            log(f'  {code}/RUB: {investing[code]}')
        else:
            log(f'  {code}/RUB: rate not found in JSON-LD')

    if investing:
        data['investing'] = investing
        log(f'Investing (RUB/unit): {investing}')
    else:
        log('Investing: all RUB-pairs failed')
except Exception as e:
    log(f'Investing error: {e}')

# ─── 3. Cross-rates from Investing.com (USD/unit) ────────
try:
    cross_pairs = {
        'EUR': 'https://www.investing.com/currencies/eur-usd',   # USD per 1 EUR
        'CNY': 'https://www.investing.com/currencies/usd-cny',   # CNY per 1 USD → invert
        'TRY': 'https://www.investing.com/currencies/usd-try',   # TRY per 1 USD → invert
    }
    xe = {}
    for code, url in cross_pairs.items():
        html = curl_get(url)
        if not html:
            log(f'  {code}: empty response')
            continue
        qa = parse_jsonld(html)
        rate = parse_rate_from_qa(qa, 'Exchange Rate')
        if rate and rate > 0:
            if code == 'EUR':
                xe[code] = round(rate, 4)       # EUR/USD = USD per 1 EUR
            else:
                xe[code] = round(1.0 / rate, 4) # USD/CNY → USD per 1 CNY
            log(f'  {code}/USD: {xe[code]}')
        else:
            log(f'  {code}: rate not found')

    if xe:
        data['xe'] = xe
        log(f'Cross-rates (USD/unit): {xe}')
    else:
        log('Cross-rates: all failed')
except Exception as e:
    log(f'Cross-rates error: {e}')

# ─── 4. XFeepay ───────────────────────────────────────────
try:
    import requests as req_xfee
    xfee = {}
    for code in ['CNH', 'EUR']:
        try:
            url = f'https://xfeepay.com/e-core/api/exchange/channelRate?sourceCurrency=USD&targetCurrency={code}'
            r = req_xfee.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            d = r.json()
            rt = d.get('data', {}).get('realTimeRate')
            if rt and rt > 0:
                xfee[code] = round(rt, 4)
                log(f'XFee {code}: {xfee[code]}')
        except Exception as e:
            log(f'XFee {code}: {e}')
    if xfee:
        data['xfee'] = xfee
        log(f'XFeepay: {xfee}')
    else:
        log('XFeepay: all failed')
except Exception as e:
    log(f'XFeepay error: {e}')

# ─── 5. Fallback for cross-rates (if investing failed) ────
if not data.get('xe'):
    try:
        log('Fetching fallback cross-rates from frankfurter.app...')
        r = urllib.request.urlopen('https://api.frankfurter.app/latest?from=USD', timeout=15)
        fx = json.loads(r.read())
        rates = fx.get('rates', {})
        fb = {}
        if 'EUR' in rates:
            fb['EUR'] = round(rates['EUR'], 4)  # EUR per 1 USD → invert
        if 'CNY' in rates:
            fb['CNY'] = round(1.0 / rates.get('CNY', 1), 4)
        if 'TRY' in rates:
            fb['TRY'] = round(1.0 / rates.get('TRY', 1), 4)
        if fb:
            data['xe'] = fb
            log(f'Fallback cross-rates: {fb}')
    except Exception as e:
        log(f'Fallback error: {e}')

# ─── Save ─────────────────────────────────────────────────
data['updated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
with open(RATES_FILE, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
log(f'Saved to {RATES_FILE}')
