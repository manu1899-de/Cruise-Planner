import json, re, time, html, os, random, subprocess, math

BASE = "https://www.icruise.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
D = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(D, "search_state.json")
OUT = os.path.join(D, "sailings.jsonl")
LOG = os.path.join(D, "search_log.txt")
PAUSE = float(os.environ.get("PAUSE", "20"))
DEADLINE = time.time() + float(os.environ.get("MAXSECS", "1700"))

# Prioridad de Manuel: MSC y Royal Caribbean 10+ noches (cualquier destino), y
# MSC/Royal <10 noches solo si son de Europa. Cada "job" es una búsqueda global
# (no por barco) que devuelve muchos barcos de una sola vez.
JOBS = [
    dict(label="Royal Caribbean 10+ noches", vendor=17, duration="10-15,15-999", dest=None),
    dict(label="MSC 10+ noches", vendor=28, duration="10-15,15-999", dest=None),
    dict(label="Royal Caribbean <10 noches, Europa", vendor=17, duration="1-2,3-5,6-9", dest=39),
    dict(label="MSC <10 noches, Europa", vendor=28, duration="1-2,3-5,6-9", dest=39),
]


def log(m):
    with open(LOG, "a") as f:
        f.write(time.strftime("%H:%M:%S ") + m + "\n")


def get(url):
    cmd = ["curl", "-sS", "-L", "-A", UA, "--max-time", "60", url]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
    return r.stdout


def blocked(s):
    return len(s) < 2000 and "Incapsula" in s


def polite_get(url):
    for attempt in range(3):
        time.sleep(PAUSE + random.uniform(0, 4))
        s = get(url)
        if not blocked(s):
            return s
        wait = 120 * (attempt + 1)
        log(f"challenge on {url[:100]} -> waiting {wait}s")
        time.sleep(wait)
    return None


def clean(x):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()


# El listado de busqueda devuelve el nombre "oficial" de la linea (ej "Royal Caribbean Cruises",
# "MSC Cruises"), pero ships.json / cw_data.json usan la forma corta ("Royal Caribbean", "MSC").
# Normalizamos para que la continuidad del historial de precios y el flag "loyalty" en gen.py sigan
# funcionando igual que con el crawler por barco.
LINE_NORMALIZE = {
    "Royal Caribbean Cruises": "Royal Caribbean",
    "MSC Cruises": "MSC",
}


def parse_rows(s):
    out = []
    for r in re.split(r"<tr>", s)[1:]:
        if 'data-getcid="' not in r:
            continue
        cid = re.search(r'data-getcid="(\d+)"', r)
        date = clean((re.search(r'celldata depart"><h2>([^<]+)</h2>', r) or [None, ""])[1])
        title = clean((re.search(r'celldata itin2"><h2>([^<]+)</h2>', r) or [None, ""])[1])
        ship = clean((re.search(r'<div class="ship">([^<]+)</div>', r) or [None, ""])[1])
        line = clean((re.search(r'<div class="line">([^<]+)</div>', r) or [None, ""])[1])
        start = clean((re.search(r'<div class="start"><b>Starts: </b>([^<]+)</div>', r) or [None, ""])[1])
        end = clean((re.search(r'<div class="end"><b>Ends: </b>([^<]+)</div>', r) or [None, ""])[1])
        ports = clean((re.search(r'<div class="port_list">([^<]*)</div>', r) or [None, ""])[1])
        nights = re.search(r'celldata length"><h2>(\d+)\s*Night', r)
        price = re.search(r'celldata price">[\s\S]*?<h2>\$([\d,]+)</h2>', r)
        url_m = re.search(r'href="(/itineraries/[^"]+\.html)', r)
        promos = [clean(p) for p in re.findall(r'title="Click to Open - Click to Close">([^<]+)</a>', r)]
        shipslug = ship.lower().replace(" ", "-").replace("'", "")
        line = LINE_NORMALIZE.get(line, line)
        out.append(dict(
            line=line, shipSlug=shipslug, ship=ship,
            dateText=date, title=title, fromTo=f"From {start} to {end}",
            ports=[p.strip() for p in ports.split(",") if p.strip()],
            nights=int(nights[1]) if nights else None,
            cid=cid[1] if cid else None,
            usd=int(price[1].replace(",", "")) if price else None,
            cabin=None, promos=promos,
            url=(BASE + url_m[1]) if url_m else None))
    return out


def job_url(j, page):
    parts = [f"Duration={j['duration']}", f"WMPHVendorCode={j['vendor']}", "ResultsPerPage=100",
              "DoDestinationSubs=y", "VacationType=1", f"PageNumber={page}"]
    if j.get("dest"):
        parts.append(f"WMPHDestinationCodeSub={j['dest']}")
    return f"{BASE}/c/src.php?" + "&".join(parts)


def main():
    st = json.load(open(STATE)) if os.path.exists(STATE) else {"done": [], "page": {}}
    for j in JOBS:
        key = j["label"]
        if key in st["done"]:
            continue
        if time.time() > DEADLINE:
            log("deadline reached, stopping (resume later)")
            break
        page = st["page"].get(key, 1)
        total_pages = None
        n_rows = 0
        stop = False
        while True:
            if time.time() > DEADLINE:
                stop = True
                break
            s = polite_get(job_url(j, page))
            if s is None:
                log(f"blocked on {key} page {page}; stopping this job for now")
                stop = True
                break
            if total_pages is None:
                m = re.search(r'([\d,]+)\s*Matched Sailings', s)
                total = int(m[1].replace(",", "")) if m else 0
                total_pages = max(1, math.ceil(total / 100))
                log(f"{key}: {total} matched sailings, {total_pages} paginas")
            rows = parse_rows(s)
            with open(OUT, "a") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n_rows += len(rows)
            page += 1
            st["page"][key] = page
            json.dump(st, open(STATE, "w"))
            if page > total_pages or not rows:
                break
        if stop:
            json.dump(st, open(STATE, "w"))
            continue
        st["done"].append(key)
        json.dump(st, open(STATE, "w"))
        log(f"{key}: listo, {n_rows} filas")
    log(f"run end: {len(st['done'])}/{len(JOBS)} jobs done")


if __name__ == "__main__":
    main()
