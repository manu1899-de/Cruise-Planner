import json, re, time, html, sys, os, random, subprocess
from urllib.parse import quote

BASE = "https://www.icruise.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
D = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(D, "state.json")
OUT = os.path.join(D, "sailings.jsonl")
LOG = os.path.join(D, "log.txt")
PAUSE = float(os.environ.get("PAUSE", "15"))
DEADLINE = time.time() + float(os.environ.get("MAXSECS", "6600"))

def log(m):
    with open(LOG, "a") as f: f.write(time.strftime("%H:%M:%S ") + m + "\n")

def get(url, referer=None):
    cmd = ["curl", "-sS", "-L", "-A", UA, "--max-time", "60", url]
    if referer: cmd[1:1] = ["-e", referer]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
    return r.stdout

def blocked(s):
    return len(s) < 2000 and "Incapsula" in s

def polite_get(url, referer=None):
    for attempt in range(3):
        time.sleep(PAUSE + random.uniform(0, 4))
        s = get(url, referer)
        if not blocked(s):
            return s
        wait = 120 * (attempt + 1)
        log(f"challenge on {url[:90]} -> waiting {wait}s")
        time.sleep(wait)
    return None

def clean(x):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()

def parse_rows(s, ship_slug, line):
    out = []
    for r in re.split(r"<tr>", s)[1:]:
        m_link = re.search(r'href="(/itineraries/[^"]+\.html)"', r)
        if not m_link: continue
        date = clean((re.search(r'celldata depart">\s*<div class="h4">([^<]+)', r) or [None, ""])[1])
        title = clean((re.search(r'celldata itinerary">\s*<div class="h4">([^<]+)', r) or [None, ""])[1])
        fromto = clean((re.search(r'<p class="sub">([\s\S]*?)</p>', r) or [None, ""])[1])
        ports = clean((re.search(r'<b>Ports:</b>([\s\S]*?)</p>', r) or [None, ""])[1])
        nights = re.search(r'celldata length">\s*<div class="h4">(\d+)', r)
        cid = re.search(r'data-getcid="(\d+)"', r)
        price = re.search(r'celldata price">[\s\S]*?\$([\d,]+)', r)
        cabin = re.search(r'celldata price">[\s\S]*?<p class="center">\s*([A-Za-z ]+?)\s*<span', r)
        promos = [clean(p) for p in re.findall(r"title=\"Click to Open - Click to Close\">([^<]+)</a>", r)]
        shipname = re.search(r'data-shipname="([^"]+)"', r)
        out.append(dict(
            line=line, shipSlug=ship_slug, ship=html.unescape(shipname[1]) if shipname else "",
            dateText=date, title=title, fromTo=fromto,
            ports=[p.strip() for p in ports.split(",") if p.strip()],
            nights=int(nights[1]) if nights else None, cid=cid[1] if cid else None,
            usd=int(price[1].replace(",", "")) if price else None,
            cabin=cabin[1].strip() if cabin else None, promos=promos, url=BASE + m_link[1]))
    return out

def main():
    cat = json.load(open(os.path.join(D, "ships.json")))  # [{slug,line,url}]
    st = json.load(open(STATE)) if os.path.exists(STATE) else {"done": [], "codes": {}}
    for sh in cat:
        if time.time() > DEADLINE:
            log("deadline reached, stopping (resume later)"); break
        slug = sh["slug"]
        if slug in st["done"]: continue
        codes = st["codes"].get(slug)
        if not codes:
            page = polite_get(sh["url"])
            if page is None:
                log(f"blocked on ship page {slug}; stopping"); break
            m = re.search(r"WMPHShipCode=(\d+)&WMPHVendorCode=(\d+)", page)
            if not m:
                log(f"no codes for {slug}; skipping"); st["done"].append(slug); json.dump(st, open(STATE, "w")); continue
            codes = [m[1], m[2]]; st["codes"][slug] = codes; json.dump(st, open(STATE, "w"))
        n_rows = 0; pnum = st.get("page", {}).get(slug, 1); stop = False
        while True:
            if time.time() > DEADLINE: stop = True; break
            url = (f"{BASE}/c/ajaxGetShipItins.php?PageNumber={pnum}&WMPHDestinationCodeSub=NULL&WMPHShipCode={codes[0]}"
                   f"&WMPHVendorCode={codes[1]}&travelDate=&sortBy=&CruiseType=1&Compare=&Sail_DateFrom=&Sail_DateTo="
                   f"&WMPHPortCode=&FormLocation=23&originPage=src&fromPageSrcType=34")
            s = polite_get(url, sh["url"])
            if s is None:
                log(f"blocked on {slug} page {pnum}; stopping"); stop = True; break
            rows = parse_rows(s, slug, sh["line"])
            if not rows: break
            with open(OUT, "a") as f:
                for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n_rows += len(rows); pnum += 1
            st.setdefault("page", {})[slug] = pnum; json.dump(st, open(STATE, "w"))
            if len(rows) < 20: break
        if stop:
            json.dump(st, open(STATE, "w")); break
        st["done"].append(slug); json.dump(st, open(STATE, "w"))
        log(f"{sh['line']} {slug}: {n_rows} rows")
    log(f"run end: {len(st['done'])}/{len(cat)} ships done")

if __name__ == "__main__":
    main()
