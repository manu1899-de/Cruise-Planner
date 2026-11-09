import json, re, datetime, os, sys

D = os.path.dirname(os.path.abspath(__file__))
# PREV_OUTPUT is the source of price-history/settings continuity from the previous run.
# It can be either a built Cruise Watch.html (parses out window.CW_DATA=...) or a plain
# cw_data.json file (the same data, saved directly) — picked by its extension.
PREV_OUTPUT = os.environ.get("PREV_OUTPUT", "/home/claude/CRUISE/Cruise Watch.html")
TEMPLATE = os.path.join(D, "template.html")  # always the current HTML/CSS/JS shell
OUT = os.environ.get("OUT", "/home/claude/CRUISE/Cruise Watch.html")
FX = float(os.environ.get("FX", "1.1439"))
TODAY = os.environ.get("TODAY", "2026-11-05")
MON = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}

EUROPE = {"Spain", "Italy", "France", "Greece", "Germany", "Netherlands", "The Netherlands", "Belgium", "United Kingdom", "England",
          "Scotland", "Ireland", "Portugal", "Norway", "Denmark", "Sweden", "Finland", "Estonia", "Latvia", "Lithuania", "Poland",
          "Croatia", "Montenegro", "Malta", "Iceland", "Monaco", "Slovenia", "Turkey", "Cyprus", "Albania", "Gibraltar", "Faroe Islands"}
GREEK = ["santorini", "mykonos", "piraeus", "athens", "rhodes", "corfu", "katakolon", "heraklion", "chania", "souda", "argostoli",
         "kefalonia", "zakynthos", "patmos", "nafplio", "volos", "thessaloniki", "crete", "milos", "syros", "kos", "chios",
         "hydra", "monemvasia", "lavrion", "itea", "skiathos", "paros", "naxos", "agios nikolaos", "gythion", "pylos", "preveza"]
SA_PORT_COUNTRY = {
    "buenos aires": "AR", "puerto madryn": "AR", "ushuaia": "AR", "montevideo": "UY", "punta del este": "UY",
    "rio de janeiro": "BR", "santos": "BR", "buzios": "BR", "ilhabela": "BR", "salvador": "BR", "recife": "BR", "fortaleza": "BR",
    "maceio": "BR", "ilheus": "BR", "itajai": "BR", "porto belo": "BR", "balneario camboriu": "BR", "manaus": "BR", "santarem": "BR",
    "parintins": "BR", "boca da valeria": "BR", "belem": "BR", "alter do chao": "BR", "angra dos reis": "BR", "paranagua": "BR",
    "punta arenas": "CL", "puerto montt": "CL", "puerto chacabuco": "CL", "valparaiso": "CL", "san antonio": "CL", "arica": "CL",
    "iquique": "CL", "coquimbo": "CL", "la serena": "CL", "callao": "PE", "lima": "PE", "salaverry": "PE", "pisco": "PE", "paracas": "PE",
    "manta": "EC", "guayaquil": "EC", "cartagena": "CO", "santa marta": "CO", "port stanley": "FK", "stanley": "FK",
    "devil's island": "GF", "iles du salut": "GF"}
ALASKA = ["juneau", "ketchikan", "skagway", "sitka", "icy strait", "glacier bay", "hubbard glacier", "tracy arm", "haines",
          "seward", "whittier", "endicott arm", "college fjord", "wrangell"]


def iso(t):
    m = re.match(r"([A-Z][a-z]{2})\w* (\d{1,2}), (\d{4})", t or "")
    return f"{m[3]}-{MON[m[1]]:02d}-{int(m[2]):02d}" if m else None


def split_fromto(ft):
    m = re.match(r"From (.+?) to (.+)$", ft or "")
    if not m: return None, None
    return m[1].strip(), m[2].strip()


def country(place):
    return place.rsplit(",", 1)[-1].strip() if place and "," in place else ""


def port_name(place):
    return place.split(",")[0].strip() if place else ""


def load():
    seen = {}
    for line in open(os.path.join(D, "sailings.jsonl")):
        r = json.loads(line)
        k = r.get("cid") or r["url"]
        seen[k] = r
    return list(seen.values())


def load_cid2gid():
    p = os.path.join(D, "cid2gid.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def load_details_full():
    p = os.path.join(D, "details_full.jsonl")
    if not os.path.exists(p):
        return {}
    out = {}
    for line in open(p):
        d = json.loads(line)
        out[d["gid"]] = d
    return out


def load_ship_specs():
    p = os.path.join(D, "ship_specs.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def apply_day_details(c, cid_bare, dep_date, cid2gid, details_full):
    # Aplica el dia a dia (cid2gid.json + details_full.jsonl) a un crucero `c`, corriendo
    # las fechas del itinerario guardado para que calcen con su fecha de zarpe real. Se usa
    # tanto para los cruceros recien crawleados hoy como para los que se "cargan" de
    # cw_data.json sin re-chequear (ver carried-over mas abajo): asi, si fill_days.py agrega
    # un itinerario nuevo, se aplica aunque el crucero en cuestion no se haya vuelto a
    # crawlear ese dia.
    gid = cid2gid.get(cid_bare)
    det = details_full.get(gid) if gid else None
    if not det or not det.get("days"):
        return False
    src_days = det["days"]
    offset0 = 0
    if src_days and src_days[0].get("date"):
        try:
            offset0 = (datetime.date.fromisoformat(dep_date) - datetime.date.fromisoformat(src_days[0]["date"])).days
        except Exception:
            offset0 = 0
    new_days = []
    for d in src_days:
        nd = dict(d)
        if d.get("date"):
            try:
                nd["date"] = (datetime.date.fromisoformat(d["date"]) + datetime.timedelta(days=offset0)).isoformat()
            except Exception:
                pass
        new_days.append(nd)
    c["days"] = new_days
    c["countries"] = det["countries"]
    if det.get("map"): c["map"] = det["map"]
    if det.get("title"): c["title"] = det["title"]
    return True


def classify(c):
    cats = []
    u, n = c["usd"], c["nights"]
    if u is None: return cats
    e = u / FX
    dep_c, arr_c = c["depCountry"], c["arrCountry"]
    low = " ".join(c["ports"]).lower() + " " + c["title"].lower()
    if 6 <= n <= 9 and dep_c in EUROPE and arr_c in EUROPE and e <= 600: cats.append("s69")
    if 10 <= n <= 12 and e <= 800: cats.append("s1012")
    if n >= 13 and u <= 1000: cats.append("s13")
    if n >= 6 and any(a in low for a in ALASKA) and c["dep"]["port"] == c["arr"]["port"] and u / n <= 110: cats.append("alaska")
    cs = {SA_PORT_COUNTRY[p] for p in SA_PORT_COUNTRY if p in low}
    trans = "transatlantic" in low or (dep_c in EUROPE) != (arr_c in EUROPE)
    if len(cs) >= 3 and not trans: cats.append("sa")
    if any(g in low for g in GREEK) and u / n <= 100: cats.append("greek")
    if dep_c == "Germany" and arr_c == "Germany": cats.append("de")
    return cats


def main():
    raw = load()
    cid2gid = load_cid2gid()
    details_full = load_details_full()
    ship_specs = load_ship_specs()
    tpl = open(TEMPLATE).read()
    old = {"settings": {}, "cruises": [], "flags": {}}
    if os.path.exists(PREV_OUTPUT):
        prev = open(PREV_OUTPUT).read()
        if PREV_OUTPUT.endswith(".json"):
            try:
                old = json.loads(prev)
            except Exception:
                pass
        elif "window.CW_DATA=" in prev:
            pa = prev.index("window.CW_DATA=") + len("window.CW_DATA=")
            pb = prev.index(";</script>", pa)
            try:
                old = json.loads(prev[pa:pb])
            except Exception:
                pass
    st = old.get("settings") or {}
    st.setdefault("fx", FX)
    st.setdefault("rules", [])
    st.setdefault("instructions", "")
    st.setdefault("scope", {"minNights": 6, "maxPriceUsd": 2000, "longNights": 18, "excludeLines": []})
    ships_info = {(c["ship"]): (c.get("built"), c.get("refurb")) for c in old.get("allCruisesSeed", old["cruises"])}
    known_by_id = {c.get("id"): c for c in old["cruises"] if c.get("id")}
    scope = st.get("scope", {})
    cruises, hidden = [], 0
    n_detail, n_specs = 0, 0
    for r in raw:
        dep_date = iso(r["dateText"])
        if not dep_date or not r.get("nights") or dep_date < TODAY: continue
        dep, arr = split_fromto(r["fromTo"])
        c = dict(id="ic-" + (r["cid"] or re.sub(r"\W", "", r["url"])[-30:]), line=r["line"], ship=r["ship"],
                 nights=r["nights"], title=r["title"], ports=r["ports"], portsComplete=True, cabin=r["cabin"] or "—",
                 url=r["url"], promos=r["promos"],
                 dep=dict(date=dep_date, port=port_name(dep)), depCountry=country(dep),
                 arr=dict(date=(datetime.date.fromisoformat(dep_date) + datetime.timedelta(days=r["nights"])).isoformat(),
                          port=port_name(arr)), arrCountry=country(arr),
                 firstSeen=TODAY, lastSeen=TODAY, status="activo")
        today_entry = dict(date=TODAY, usd=r["usd"], eur=round(r["usd"] / FX, 2) if r["usd"] else None, fx=FX)
        pc = known_by_id.get(c["id"])
        if pc:
            hist = list(pc.get("history") or [])
            if hist and hist[-1].get("date") == TODAY:
                hist[-1] = today_entry  # re-running the same day: replace, don't duplicate
            elif hist and hist[-1].get("usd") == today_entry["usd"]:
                pass  # price unchanged since the last recorded change: keep history as-is
            else:
                hist.append(today_entry)  # real price change (or first time price is known): log it
            c["history"] = hist[-120:]
            c["firstSeen"] = pc.get("firstSeen", TODAY)
            c["baseline"] = pc.get("baseline", True)
        else:
            c["history"] = [today_entry]
            c["baseline"] = not old["cruises"]  # only the very first run counts as baseline
        bi = ships_info.get(r["ship"])
        if bi: c["built"], c["refurb"] = bi
        specs = ship_specs.get(r.get("shipSlug"))
        if specs:
            if specs.get("Year Built"): c["built"] = specs["Year Built"]
            if specs.get("Year Refurbished"): c["refurb"] = specs["Year Refurbished"]
            if specs.get("Tonnage"): c["tonnage"] = specs["Tonnage"] + " GT"
            if specs.get("Passengers (Max Occupancy)"): c["capacity"] = specs["Passengers (Max Occupancy)"]
            n_specs += 1
        if apply_day_details(c, r.get("cid"), dep_date, cid2gid, details_full):
            n_detail += 1
        c["loyalty"] = r["line"] if r["line"] in ("Royal Caribbean", "MSC") else None
        u = r["usd"]
        c["usd"] = u
        if c["nights"] < scope.get("minNights", 6) or (u is not None and u >= scope.get("maxPriceUsd", 2000) and not c["nights"] > scope.get("longNights", 18)):
            hidden += 1
            continue
        # Signature used to spot icruise.com publishing a second cid for the same physical
        # sailing (same ship, same departure day, same length, same arrival) -- usually
        # because a port call changed and the old listing was never taken down. Deliberately
        # excludes `ports`, since that's exactly what can differ between the duplicates.
        c["key"] = f"{c['ship']}|{dep_date}|{c['nights']}|{c['arr']['date']}|{c['arr']['port']}"
        c["cats"] = classify(c)
        c["note"] = ("Promociones: " + "; ".join(r["promos"])) if r["promos"] else ""
        cruises.append(c)
    # Desde que el crawl diario puede cubrir solo una parte del catalogo (ver search_crawl.py:
    # algunos dias se prioriza MSC/Royal, el resto queda para otro ciclo), los cruceros que ya
    # estaban en cw_data.json pero no se volvieron a ver hoy NO se descartan: se conservan tal
    # cual (con su precio/historial de la ultima vez que se chequearon) en vez de perderse.
    seen_ids = {c["id"] for c in cruises}
    carried = 0
    carried_detail = 0
    for old_id, oc in known_by_id.items():
        if old_id in seen_ids:
            continue
        dep_date_old = (oc.get("dep") or {}).get("date")
        if not dep_date_old or dep_date_old < TODAY:
            continue  # ya zarpo, no tiene sentido seguir mostrandolo
        if not oc.get("days"):
            # no se re-chequea el precio hoy, pero si cid2gid.json/details_full.jsonl
            # ganaron un itinerario nuevo desde la ultima vez (p.ej. via fill_days.py),
            # lo aplicamos igual -- si no, un crucero sin dias podia quedar asi para
            # siempre hasta que calzara con volver a crawlearse.
            cid_bare = (old_id or "").replace("ic-", "")
            if apply_day_details(oc, cid_bare, dep_date_old, cid2gid, details_full):
                carried_detail += 1
        oc["key"] = f"{oc.get('ship')}|{dep_date_old}|{oc.get('nights')}|{(oc.get('arr') or {}).get('date')}|{(oc.get('arr') or {}).get('port')}"
        cruises.append(oc)
        carried += 1
    # icruise.com occasionally has two live cid's for what is the same physical sailing (same
    # ship, same departure day, same length, same arrival) -- usually because one port call
    # changed (e.g. Arrecife -> Puerto del Rosario) and the old listing was never taken down.
    # Showing both as separate rows is confusing and splits the price history in two, so we
    # collapse each group onto the one with the longest price history (the most tracking
    # value), folding in any price points the other copy has that aren't already recorded.
    by_sig = {}
    for c in cruises:
        by_sig.setdefault(c.get("key"), []).append(c)
    merged_count = 0
    deduped = []
    for sig, group in by_sig.items():
        if not sig or len(group) == 1:
            deduped.extend(group)
            continue
        group.sort(key=lambda c: len(c.get("history") or []), reverse=True)
        canon = group[0]
        by_date = {h["date"]: h for h in (canon.get("history") or [])}
        for other in group[1:]:
            for h in (other.get("history") or []):
                by_date.setdefault(h["date"], h)
        canon["history"] = sorted(by_date.values(), key=lambda h: h["date"])[-120:]
        canon["firstSeen"] = min([canon.get("firstSeen", TODAY)] + [o.get("firstSeen", TODAY) for o in group[1:]])
        deduped.append(canon)
        merged_count += len(group) - 1
    cruises = deduped
    if merged_count:
        print(f"duplicados fusionados (misma nave/fecha/llegada, distinto cid): {merged_count}")
    print(f"detail matched: {n_detail}/{len(raw)}, specs matched: {n_specs}/{len(raw)}")
    print(f"carried over sin re-chequear hoy: {carried} ({carried_detail} con itinerario nuevo aplicado)")
    st["lastRun"] = TODAY
    st["catalogCount"] = len(cruises) + hidden
    st["catalogStatus"] = os.environ.get("STATUS", "Línea base: primera extracción completa. NEW se calcula a partir de la próxima revisión.")
    data = dict(settings=st, cruises=cruises, flags=old.get("flags", {}), reports=[], hiddenByScope=hidden)
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    out = tpl.replace("__DATA__", data_json)
    open(OUT, "w").write(out)
    data_out = os.environ.get("DATA_OUT")
    if data_out:
        open(data_out, "w").write(data_json)
    from collections import Counter
    cc = Counter(k for c in cruises for k in c["cats"])
    print(f"{len(cruises)} in scope, {hidden} hidden, file {len(out)/1e6:.1f} MB, cats {dict(cc)}")
    # price-change summary for the day's notification
    changes = []
    for c in cruises:
        h = c.get("history") or []
        if len(h) >= 2 and h[-1].get("usd") is not None and h[-2].get("usd") is not None and h[-1]["date"] == TODAY:
            changes.append((h[-1]["usd"] - h[-2]["usd"], c["ship"], c["line"], c["dep"]["date"], h[-2]["usd"], h[-1]["usd"], c["id"]))
    changes.sort(key=lambda x: x[0])
    if changes:
        print(f"PRICE_CHANGES: {len(changes)} cruceros cambiaron de precio hoy")
        for d, ship, line, dep, old_p, new_p, cid in changes[:15]:
            print(f"  {'▼' if d<0 else '▲'} {ship} ({line}) {dep}: {old_p}->{new_p} USD ({d:+d})")
    else:
        print("PRICE_CHANGES: 0")


if __name__ == "__main__":
    main()
