import json, re, time, html, os, random, subprocess, hashlib, sys

# Backfill puntual para cruceros a los que les falta el dia a dia (c["days"] vacio en
# cw_data.json). Esto pasa cuando icruise.com bloqueo (Incapsula) la pagina de itinerario
# la unica vez que se scrapeo originalmente para construir cid2gid.json/details_full.jsonl
# (ver README: esos archivos "casi no cambian, no se vuelven a crawlear a diario").
#
# Agrupa los cruceros con days faltante por (barco, noches, paradas) -- muchos cruceros
# distintos (mismas fechas futuras repetidas de la misma ruta) comparten identico
# itinerario, asi que alcanza con bajar UNA pagina de ejemplo por grupo y aplicar ese
# itinerario (con las fechas corridas) a todos los cid del grupo via cid2gid.json.
#
# Uso:
#   python3 -I fill_days.py fetch   # baja 1 pagina por grupo faltante a raw_days_cache/
#   python3 -I fill_days.py build   # parsea lo bajado y escribe cid2gid.json + details_full.jsonl

BASE = "https://www.icruise.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
D = os.path.dirname(os.path.abspath(__file__))
CW_DATA = os.path.join(D, "cw_data.json")
CID2GID = os.path.join(D, "cid2gid.json")
DETAILS_FULL = os.path.join(D, "details_full.jsonl")
CACHE_DIR = os.path.join(D, "raw_days_cache")
STATE = os.path.join(D, "fill_days_state.json")
LOG = os.path.join(D, "fill_days_log.txt")
PAUSE = float(os.environ.get("PAUSE", "20"))

MESES_EN = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
            "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}

# Traduccion ingles->espanol de los nombres de pais tal como aparecen en icruise.com
# (formato "Ciudad, Pais" en <strong class="depart_port_title">). No es una tabla
# inventada: se construyo leyendo los ~130 nombres de pais en espanol que YA existen en
# details_full.jsonl (datos del scrape original) y emparejandolos con su nombre en ingles
# estandar. Si aparece un pais nuevo no mapeado, build() lo deja en ingles tal cual y lo
# loguea para revision manual -- nunca inventa una traduccion.
COUNTRY_ES = {
    "United States": "Estados Unidos", "USA": "Estados Unidos",
    "Alaska": "Estados Unidos", "Hawaii": "Estados Unidos",
    "Mexico": "México", "Canada": "Canadá", "Bahamas": "Bahamas",
    "Jamaica": "Jamaica", "Belize": "Belice", "Honduras": "Honduras",
    "Cayman Islands": "Islas Caimán", "Puerto Rico": "Puerto Rico (EE. UU.)",
    "US Virgin Islands": "Islas Vírgenes de EE. UU.",
    "United States Virgin Islands": "Islas Vírgenes de EE. UU.",
    "British Virgin Islands": "Islas Vírgenes Británicas",
    "Netherlands Antilles": "Antillas Neerlandesas",
    "St. Kitts and Nevis": "San Cristóbal y Nieves",
    "St. Kitts & Nevis": "San Cristóbal y Nieves",
    "St. Lucia": "Santa Lucía",
    "Turks and Caicos Islands": "Islas Turcas y Caicos",
    "Dominican Republic": "República Dominicana",
    "Aruba": "Aruba", "Curacao": "Curazao", "Bonaire": "Bonaire",
    "Grenada": "Granada", "Barbados": "Barbados",
    "Antigua and Barbuda": "Antigua y Barbuda", "Dominica": "Dominica",
    "Trinidad and Tobago": "Trinidad y Tobago", "Colombia": "Colombia",
    "Panama": "Panamá", "Costa Rica": "Costa Rica", "Ecuador": "Ecuador",
    "Guatemala": "Guatemala", "Haiti": "Haití", "El Salvador": "El Salvador",
    "St. Vincent and the Grenadines": "San Vicente y las Granadinas",
    "St. Vincent & The Grenadines": "San Vicente y las Granadinas",
    "St. Barthelemy": "San Bartolomé (Francia)", "St. Barts": "San Bartolomé (Francia)",
    "St. Helena": "Santa Elena",
    "Virgin Islands - British": "Islas Vírgenes Británicas",
    "Guadeloupe": "Guadalupe (Francia)", "Guadaloupe": "Guadalupe (Francia)",
    "Martinique": "Martinica (Francia)",
    "Reunion": "Reunión (Francia)", "French Guiana": "Guayana Francesa",
    "Spain": "España", "France": "Francia", "Italy": "Italia",
    "Greece": "Grecia", "Croatia": "Croacia", "Montenegro": "Montenegro",
    "Malta": "Malta", "Cyprus": "Chipre", "Turkey": "Turquía",
    "Portugal": "Portugal", "Monaco": "Mónaco", "Slovenia": "Eslovenia",
    "Slovakia": "Eslovaquia", "Hungary": "Hungría",
    "Albania": "Albania", "United Kingdom": "Reino Unido", "Scotland": "Escocia",
    "Ireland": "Irlanda", "Norway": "Noruega", "Sweden": "Suecia",
    "Denmark": "Dinamarca", "Finland": "Finlandia", "Germany": "Alemania",
    "Netherlands": "Países Bajos", "Belgium": "Bélgica", "Iceland": "Islandia",
    "Estonia": "Estonia", "Latvia": "Letonia", "Lithuania": "Lituania",
    "Faroe Islands": "Islas Feroe", "Greenland": "Groenlandia",
    "Austria": "Austria", "Switzerland": "Suiza",
    "Poland": "Polonia", "Russia": "Rusia", "Morocco": "Marruecos",
    "Tunisia": "Túnez", "Algeria": "Argelia", "Egypt": "Egipto", "Israel": "Israel",
    "Jordan": "Jordania", "Gibraltar": "Gibraltar",
    "United Arab Emirates": "Emiratos Árabes Unidos", "Oman": "Omán",
    "Qatar": "Catar", "Saudi Arabia": "Arabia Saudita", "Bahrain": "Bahrein",
    "Kuwait": "Kuwait", "India": "India", "Sri Lanka": "Sri Lanka",
    "Maldives": "Maldivas",
    "Japan": "Japón", "China": "China", "Hong Kong": "Hong Kong",
    "Taiwan": "Taiwán", "South Korea": "Corea del Sur",
    "Vietnam": "Vietnam", "Thailand": "Tailandia", "Cambodia": "Camboya",
    "Myanmar": "Birmania (Myanmar)", "Burma": "Birmania (Myanmar)",
    "Philippines": "Filipinas", "Malaysia": "Malasia",
    "Singapore": "Singapur", "Indonesia": "Indonesia",
    "Australia": "Australia", "New Zealand": "Nueva Zelanda",
    "Papua New Guinea": "Papúa Nueva Guinea", "Fiji": "Fiyi",
    "French Polynesia": "Polinesia Francesa", "New Caledonia": "Nueva Caledonia",
    "Solomon Islands": "Islas Salomón", "Vanuatu": "Vanuatu",
    "Cook Islands": "Islas Cook", "Samoa": "Samoa",
    "American Samoa": "Samoa Americana", "Tonga": "Tonga", "Kiribati": "Kiribati",
    "Brazil": "Brasil", "Argentina": "Argentina", "Chile": "Chile", "Uruguay": "Uruguay",
    "Peru": "Perú", "Falkland Islands": "Islas Malvinas", "Antarctica": "Antártida",
    "South Africa": "Sudáfrica", "Namibia": "Namibia", "Mozambique": "Mozambique",
    "Kenya": "Kenia", "Madagascar": "Madagascar", "Mauritius": "Mauricio",
    "Seychelles": "Seychelles", "Ivory Coast": "Costa de Marfil",
    "Cote d'Ivoire": "Costa de Marfil", "Gambia": "Gambia",
    "Senegal": "Senegal", "Cape Verde": "Cabo Verde",
    "Bermuda": "Bermudas", "Pitcairn Islands": "Islas Pitcairn", "Pitcairn": "Pitcairn",
}


def log(m):
    with open(LOG, "a") as f:
        f.write(time.strftime("%H:%M:%S ") + m + "\n")
    print(m)


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


def missing_groups():
    cw = json.load(open(CW_DATA))
    missing = [c for c in cw["cruises"] if not c.get("days")]
    groups = {}
    for c in missing:
        key = (c["ship"], c["nights"], tuple(c.get("ports", [])))
        groups.setdefault(key, []).append(c)
    out = []
    for key, members in groups.items():
        rep = next((m for m in members if m.get("url")), None)
        if not rep:
            continue
        out.append({
            "key": "|".join(map(str, key)) if False else repr(key),
            "ship": key[0], "nights": key[1], "ports": list(key[2]),
            "rep_cid": rep["id"], "rep_url": rep["url"],
            "cids": [m["id"] for m in members],
        })
    return out


def cmd_fetch():
    os.makedirs(CACHE_DIR, exist_ok=True)
    groups = missing_groups()
    state = json.load(open(STATE)) if os.path.exists(STATE) else {"done": [], "failed": []}
    log(f"fetch start: {len(groups)} grupos, {len(state['done'])} ya hechos")
    for g in groups:
        cid = g["rep_cid"]
        cache_path = os.path.join(CACHE_DIR, f"{cid}.html")
        if cid in state["done"] or os.path.exists(cache_path):
            continue
        s = polite_get(g["rep_url"])
        if s is None or blocked(s):
            state.setdefault("failed", [])
            if cid not in state["failed"]:
                state["failed"].append(cid)
            json.dump(state, open(STATE, "w"))
            log(f"{cid}: bloqueado, no se pudo bajar")
            continue
        with open(cache_path, "w") as f:
            f.write(s)
        state["done"].append(cid)
        if cid in state.get("failed", []):
            state["failed"].remove(cid)
        json.dump(state, open(STATE, "w"))
        log(f"{cid} ({g['ship']}, {g['nights']}n): OK ({len(s)} bytes)")
    n_ok = len([g for g in groups if os.path.exists(os.path.join(CACHE_DIR, f'{g["rep_cid"]}.html'))])
    log(f"fetch end: {n_ok}/{len(groups)} paginas en cache")


def clean(x):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()


DAY_RE = re.compile(
    r'<div class="day\s+onCruiseTitle\s*">([A-Za-z]+)\s*-\s*([A-Za-z]+)\s+(\d+),\s+(\d{4})</div>'
    r'.*?<div class="port_detail_itin_date">Day<br><span>(\d+)</span></div>'
    r'.*?<strong class="depart_port_title">([^<]+)</strong>'
    r'(.*?)</ul>',
    re.DOTALL)

ARR_RE = re.compile(r'<strong>Arrive:</strong>\s*(\d{2}:\d{2}):\d{2}')
DEP_RE = re.compile(r'<strong>Depart:</strong>\s*(\d{2}:\d{2}):\d{2}')
TITLE_RE = re.compile(r'<div class="summary-title"><h1>([^<]+)</h1>')
MAP_RE = re.compile(r'image_map\s*:\s*"([^"]+)"')


def parse_page(s):
    title_m = TITLE_RE.search(s)
    title = html.unescape(title_m[1]).strip() if title_m else ""
    map_m = MAP_RE.search(s)
    map_url = map_m[1] if map_m else None

    days = []
    unmapped_countries = set()
    for m in DAY_RE.finditer(s):
        mon, mon2, day_num, year, day_n, port_raw, rest = m.groups()
        mon3 = mon2[:3]
        if mon3 not in MESES_EN:
            continue
        date = f"{int(year):04d}-{MESES_EN[mon3]:02d}-{int(day_num):02d}"
        port_raw = html.unescape(port_raw).strip()
        if "," in port_raw:
            port, country_en = [p.strip() for p in port_raw.split(",", 1)]
        else:
            port, country_en = port_raw, ""
        if port == "At Sea":
            country = ""
        elif not country_en:
            country = ""
        elif country_en in COUNTRY_ES:
            country = COUNTRY_ES[country_en]
        else:
            country = country_en
            unmapped_countries.add(country_en)
        arr_m = ARR_RE.search(rest)
        dep_m = DEP_RE.search(rest)
        days.append({
            "date": date, "port": port, "country": country,
            "arr": arr_m[1] if arr_m else None,
            "dep": dep_m[1] if dep_m else None,
        })
    countries = []
    for d in days:
        if d["country"] and d["country"] not in countries:
            countries.append(d["country"])
    return title, days, countries, map_url, unmapped_countries


def gid_for(key, existing_gids):
    base = hashlib.md5(repr(key).encode()).hexdigest()[:12]
    gid = base
    salt = 0
    while gid in existing_gids:
        salt += 1
        gid = hashlib.md5((repr(key) + str(salt)).encode()).hexdigest()[:12]
    return gid


def cmd_build():
    groups = missing_groups()
    cid2gid = json.load(open(CID2GID)) if os.path.exists(CID2GID) else {}
    existing_gids = set(cid2gid.values())
    details = []
    if os.path.exists(DETAILS_FULL):
        with open(DETAILS_FULL) as f:
            details_lines = f.readlines()
    else:
        details_lines = []

    n_built = 0
    n_skip_no_cache = 0
    n_skip_no_days = 0
    all_unmapped = set()
    new_lines = []
    for g in groups:
        cid = g["rep_cid"]
        cache_path = os.path.join(CACHE_DIR, f"{cid}.html")
        if not os.path.exists(cache_path):
            n_skip_no_cache += 1
            continue
        s = open(cache_path).read()
        title, days, countries, map_url, unmapped = parse_page(s)
        all_unmapped |= unmapped
        if not days:
            n_skip_no_days += 1
            log(f"{cid}: no se pudieron parsear dias (pagina cambio de formato?)")
            continue
        key = (g["ship"], g["nights"], tuple(g["ports"]))
        gid = gid_for(key, existing_gids)
        existing_gids.add(gid)
        rec = {"title": title, "days": days, "countries": countries, "gid": gid}
        if map_url:
            rec["map"] = map_url
        new_lines.append(json.dumps(rec, ensure_ascii=False))
        # strip "ic-" prefix the way the rest of the pipeline's cid keys do in cid2gid.json
        for full_cid in g["cids"]:
            bare = full_cid.replace("ic-", "")
            cid2gid[bare] = gid
        n_built += 1

    with open(DETAILS_FULL, "a") as f:
        for line in new_lines:
            f.write(line + "\n")
    json.dump(cid2gid, open(CID2GID, "w"), ensure_ascii=False)

    log(f"build end: {n_built} grupos nuevos escritos ({sum(len(g['cids']) for g in groups if os.path.exists(os.path.join(CACHE_DIR, g['rep_cid']+'.html')))} cruceros cubiertos), "
        f"{n_skip_no_cache} sin cache, {n_skip_no_days} sin dias parseados")
    if all_unmapped:
        log("paises sin traducir (quedaron en ingles, revisar COUNTRY_ES): " + ", ".join(sorted(all_unmapped)))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("fetch", "build"):
        print("uso: python3 -I fill_days.py [fetch|build]")
        sys.exit(1)
    if sys.argv[1] == "fetch":
        cmd_fetch()
    else:
        cmd_build()
