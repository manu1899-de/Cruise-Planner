import json, re, time, html, os, random, subprocess, datetime

# Chequea el precio actual de los cruceros que Manuel marco con la ⚑ "Guardar" en el
# dashboard (localStorage "cw-saved" en SU navegador). Como ese dato no es accesible desde
# aca, Manuel exporta de tanto en tanto un backup (boton de Exportar en el dashboard) y
# comparte el archivo; de ahi se sacan los IDs y se guardan en saved_cruises.json (solo los
# IDs de catalogo, nada personal: ni "mycruises" ni "people" se tocan ni se guardan).
#
# A diferencia de search_crawl.py (que trae muchos barcos de una sola busqueda), esto hace
# una peticion individual por crucero guardado -- son pocos, asi que es barato.

BASE = "https://www.icruise.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
D = os.path.dirname(os.path.abspath(__file__))
SAVED_IDS = os.path.join(D, "saved_cruises.json")
CW_DATA = os.path.join(D, "cw_data.json")
OUT = os.path.join(D, "sailings.jsonl")
LOG = os.path.join(D, "saved_log.txt")
PAUSE = float(os.environ.get("PAUSE", "20"))

MESES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


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
        wait = 60 * (attempt + 1)
        log(f"challenge on {url[:90]} -> waiting {wait}s")
        time.sleep(wait)
    return None


def clean(x):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()


def parse_price_cabin(s):
    # La primera fila de la tabla "itinerary-sailplan-pricing" es la categoria mas barata
    # (normalmente "Inside"), que es el mismo criterio de precio "desde" que usa el resto
    # del pipeline.
    m = re.search(
        r'id="itinerary-sailplan-pricing".*?<td class="meta-label">([^<]+)</td>.*?'
        r'<div class="meta-value-content">\$([\d,]+)</div>',
        s, re.DOTALL)
    if not m:
        return None, None
    return clean(m[1]), int(m[2].replace(",", ""))


def main():
    if not os.path.exists(SAVED_IDS):
        log("no hay saved_cruises.json, nada que hacer")
        return
    ids = json.load(open(SAVED_IDS))
    cw = json.load(open(CW_DATA)) if os.path.exists(CW_DATA) else {"cruises": []}
    by_id = {c["id"]: c for c in cw["cruises"] if c.get("id")}
    n_ok = 0
    for cid_full in ids:
        c = by_id.get(cid_full)
        if not c or not c.get("url"):
            log(f"{cid_full}: no esta en el catalogo o no tiene url, salteado")
            continue
        s = polite_get(c["url"])
        if s is None:
            log(f"{cid_full}: bloqueado, no se pudo chequear hoy")
            continue
        cabin, usd = parse_price_cabin(s)
        if usd is None:
            log(f"{cid_full}: no se encontro precio en la pagina")
            continue
        dep_date = c["dep"]["date"]
        dt = datetime.date.fromisoformat(dep_date)
        date_text = f"{MESES[dt.month - 1]} {dt.day}, {dt.year}"
        row = dict(
            line=c["line"], shipSlug=c["ship"].lower().replace(" ", "-").replace("'", ""),
            ship=c["ship"], dateText=date_text, title=c.get("title", ""),
            fromTo=f"From {c['dep']['port']}, {c['depCountry']} to {c['arr']['port']}, {c['arrCountry']}",
            ports=c.get("ports", []), nights=c["nights"], cid=cid_full.replace("ic-", ""),
            usd=usd, cabin=cabin, promos=[], url=c["url"])
        with open(OUT, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        n_ok += 1
        log(f"{cid_full} ({c['ship']}): {usd} USD ({cabin})")
    log(f"run end: {n_ok}/{len(ids)} guardados chequeados")


if __name__ == "__main__":
    main()
