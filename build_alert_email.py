import json, os, datetime, html

# Genera el correo de avisos diario (Guardados + Royal Caribbean/MSC 10+ noches bajo
# $2000) a partir de cw_data.json, que ya tiene el dia armado por gen.py. No crawlea nada
# nuevo -- corre DESPUES de que la tarea diaria de precios ya actualizo y pusheo
# cw_data.json al repositorio.
#
# Escribe 3 archivos en el directorio del script (no se versionan):
#   alert_subject.txt  -- asunto del correo (una linea)
#   alert_body.html    -- cuerpo HTML listo para mandar tal cual
#   alert_body.txt     -- version texto plano (fallback)
# y imprime por stdout "HAS_ALERTS: yes" o "HAS_ALERTS: no" como primera linea, para que
# quien orquesta el envio sepa si hace falta mandar el correo ese dia.

D = os.path.dirname(os.path.abspath(__file__))
CW_DATA = os.path.join(D, "cw_data.json")
SAVED_IDS = os.path.join(D, "saved_cruises.json")
TODAY = os.environ.get("TODAY") or datetime.date.today().isoformat()

WATCH_LINES = {"Royal Caribbean", "MSC"}
MIN_NIGHTS = 10
MAX_USD = 2000  # Manuel: "no me interesan viajes de mas de 2000 por persona"

COLORS = dict(bg="#EEF3F6", panel="#FFFFFF", ink="#0E1C26", ink2="#46596A", ink3="#7D8E9B",
              line="#D8E2E8", line2="#B9C8D2", navy="#0B2545", navy2="#13315C",
              sea="#0A8F9E", seasoft="#D5F1F3", seaink="#056470",
              coral="#E8553E", coralsoft="#FDE3DD", sun="#F2A900", sunsoft="#FFF1CC",
              green="#178A4C", greensoft="#D9F2E3", red="#C62F2F", redsoft="#FBE0E0")
F_DISPLAY = "'Bricolage Grotesque',Georgia,serif"
F_BODY = "'Public Sans',Arial,Helvetica,sans-serif"


def nfi(n):
    if n is None:
        return "—"
    return f"{round(n):,}".replace(",", ".")


def last_two(c):
    h = c.get("history") or []
    if not h:
        return None, None
    return h[-1], (h[-2] if len(h) > 1 else None)


def esc(s):
    return html.escape(str(s or ""), quote=True)


def collect():
    cw = json.load(open(CW_DATA))
    saved_ids = set(json.load(open(SAVED_IDS))) if os.path.exists(SAVED_IDS) else set()
    settings = cw.get("settings") or {}
    last_run = settings.get("lastRun")

    saved_changes, rc_msc_drops, rc_msc_new = [], [], []

    for c in cw["cruises"]:
        dep = c.get("dep") or {}
        dep_date = dep.get("date")
        if not dep_date or dep_date < TODAY:
            continue
        last, prev = last_two(c)
        changed_today = bool(
            last and prev and last.get("date") == TODAY
            and last.get("usd") is not None and prev.get("usd") is not None
            and last["usd"] != prev["usd"]
        )
        item = dict(id=c["id"], ship=c["ship"], line=c["line"], nights=c["nights"],
                    dep_date=dep_date, dep_port=dep.get("port"), title=c.get("title") or "",
                    url=c.get("url"))

        if c["id"] in saved_ids and changed_today:
            saved_changes.append(dict(item, old=prev["usd"], new=last["usd"]))

        if c.get("line") in WATCH_LINES and (c.get("nights") or 0) >= MIN_NIGHTS:
            u = c.get("usd")
            if u is not None and u < MAX_USD:
                if changed_today and last["usd"] < prev["usd"]:
                    rc_msc_drops.append(dict(item, old=prev["usd"], new=last["usd"]))
                if c.get("firstSeen") == TODAY:
                    rc_msc_new.append(dict(item, new=u))

    # lo mas barato / mayor bajada primero, para que lo mejor quede arriba
    saved_changes.sort(key=lambda x: x["new"] - x["old"])
    rc_msc_drops.sort(key=lambda x: x["new"] - x["old"])
    rc_msc_new.sort(key=lambda x: x["new"])

    return last_run, saved_changes, rc_msc_drops, rc_msc_new


def card_html(it, kind):
    sub = f"{esc(it['line'])} · {it['nights']} noches · zarpa {it['dep_date']} desde {esc(it['dep_port'] or '—')}"
    if kind == "change":
        delta = it["new"] - it["old"]
        down = delta < 0
        color = COLORS["green"] if down else COLORS["red"]
        soft = COLORS["greensoft"] if down else COLORS["redsoft"]
        arrow = "▼" if down else "▲"
        price_html = (
            f'<span style="font:13px/1 {F_BODY};color:{COLORS["ink3"]};text-decoration:line-through">{nfi(it["old"])} USD</span>'
            f'<div style="font:800 22px/1.2 {F_DISPLAY};color:{COLORS["ink"]};margin-top:2px">{nfi(it["new"])} USD'
            f' <span style="display:inline-block;font:700 13px {F_BODY};color:{color};background:{soft};'
            f'border-radius:999px;padding:3px 9px;margin-left:4px;vertical-align:middle">{arrow} {nfi(abs(delta))}</span></div>'
        )
    else:
        price_html = f'<div style="font:800 22px/1.2 {F_DISPLAY};color:{COLORS["ink"]};margin-top:2px">{nfi(it["new"])} USD</div>'

    title = it.get("title") or it["ship"]
    return f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{COLORS["panel"]};border:1px solid {COLORS["line"]};border-radius:14px;margin:0 0 10px 0">
<tr><td style="padding:16px 18px">
<div style="font:800 17px/1.3 {F_DISPLAY};color:{COLORS["navy"]}">{esc(title)}</div>
<div style="font:13px {F_BODY};color:{COLORS["ink2"]};margin-top:3px">{sub}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px"><tr>
<td style="vertical-align:middle">{price_html}</td>
<td style="text-align:right;vertical-align:middle">
<a href="{esc(it['url'])}" style="display:inline-block;background:{COLORS["coral"]};color:#fff;font:700 13px {F_BODY};text-decoration:none;border-radius:999px;padding:9px 16px;white-space:nowrap">Ver en iCruise ↗</a>
</td></tr></table>
</td></tr></table>'''


def card_text(it, kind):
    sub = f"{it['line']} · {it['nights']} noches · zarpa {it['dep_date']} desde {it['dep_port'] or '—'}"
    title = it.get("title") or it["ship"]
    if kind == "change":
        delta = it["new"] - it["old"]
        return f"- {title}\n  {sub}\n  {nfi(it['old'])} -> {nfi(it['new'])} USD ({'+' if delta > 0 else ''}{nfi(delta)})\n  {it['url']}"
    return f"- {title}\n  {sub}\n  {nfi(it['new'])} USD\n  {it['url']}"


def section_html(label, chip_color, chip_soft, items, kind):
    if not items:
        return ""
    cards = "".join(card_html(it, kind) for it in items)
    return f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:22px 0 10px 0"><tr><td>
<span style="display:inline-block;font:800 12px {F_BODY};letter-spacing:.03em;text-transform:uppercase;color:{chip_color};background:{chip_soft};border-radius:999px;padding:5px 12px">{esc(label)} · {len(items)}</span>
</td></tr></table>
{cards}'''


def build_html(today, saved_changes, rc_msc_drops, rc_msc_new):
    total = len(saved_changes) + len(rc_msc_drops) + len(rc_msc_new)
    body = (
        section_html("Tus guardados · cambio de precio", COLORS["sea"], COLORS["seasoft"], saved_changes, "change")
        + section_html("Royal Caribbean / MSC 10+ noches · bajaron de precio", COLORS["green"], COLORS["greensoft"], rc_msc_drops, "change")
        + section_html("Royal Caribbean / MSC 10+ noches · nuevos en el catálogo", COLORS["sun"], COLORS["sunsoft"], rc_msc_new, "new")
    )
    date_txt = datetime.date.fromisoformat(today).strftime("%d/%m/%Y")
    return f'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CRUISE PLANNER - avisos</title></head>
<body style="margin:0;padding:0;background:{COLORS["bg"]}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{COLORS["bg"]}">
<tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:100%">
<tr><td style="background:linear-gradient(120deg,#10231F,#163832,#1B4A42);border-radius:16px 16px 0 0;padding:22px 24px">
<div style="font:800 26px/1 {F_DISPLAY};color:#fff">CRUISE <span style="color:#FFB020">PLANNER</span></div>
<div style="font:13px {F_BODY};color:#C7D6E6;margin-top:6px">Avisos del {date_txt} · {total} novedad{"es" if total != 1 else ""}</div>
</td></tr>
<tr><td style="background:{COLORS["panel"]};border:1px solid {COLORS["line"]};border-top:0;border-radius:0 0 16px 16px;padding:8px 20px 22px 20px">
{body}
<div style="margin-top:18px;padding-top:14px;border-top:1px solid {COLORS["line"]};font:12px {F_BODY};color:{COLORS["ink3"]}">
Generado automáticamente por tu CRUISE PLANNER a partir de la actualización de precios de hoy.
</div>
</td></tr>
</table>
</td></tr>
</table>
</body></html>'''


def build_text(today, saved_changes, rc_msc_drops, rc_msc_new):
    parts = [f"CRUISE PLANNER - avisos del {today}", ""]
    if saved_changes:
        parts.append(f"TUS GUARDADOS - cambio de precio ({len(saved_changes)})")
        parts += [card_text(it, "change") for it in saved_changes]
        parts.append("")
    if rc_msc_drops:
        parts.append(f"ROYAL CARIBBEAN / MSC 10+ NOCHES - bajaron de precio ({len(rc_msc_drops)})")
        parts += [card_text(it, "change") for it in rc_msc_drops]
        parts.append("")
    if rc_msc_new:
        parts.append(f"ROYAL CARIBBEAN / MSC 10+ NOCHES - nuevos en el catalogo ({len(rc_msc_new)})")
        parts += [card_text(it, "new") for it in rc_msc_new]
        parts.append("")
    return "\n".join(parts)


def main():
    last_run, saved_changes, rc_msc_drops, rc_msc_new = collect()
    total = len(saved_changes) + len(rc_msc_drops) + len(rc_msc_new)
    has_alerts = total > 0

    subject = f"CRUISE PLANNER · avisos de hoy: {len(saved_changes)} guardado(s), {len(rc_msc_drops)} bajada(s), {len(rc_msc_new)} nuevo(s)"
    html_body = build_html(TODAY, saved_changes, rc_msc_drops, rc_msc_new)
    text_body = build_text(TODAY, saved_changes, rc_msc_drops, rc_msc_new)

    open(os.path.join(D, "alert_subject.txt"), "w").write(subject)
    open(os.path.join(D, "alert_body.html"), "w").write(html_body)
    open(os.path.join(D, "alert_body.txt"), "w").write(text_body)

    print(f"ALERT_LAST_RUN: {last_run}")
    print(f"ALERT_TODAY: {TODAY}")
    print(f"ALERT_DATA_READY: {'yes' if last_run == TODAY else 'no'}")
    print(f"HAS_ALERTS: {'yes' if has_alerts else 'no'}")
    print(f"COUNTS: guardados={len(saved_changes)} bajadas={len(rc_msc_drops)} nuevos={len(rc_msc_new)}")


if __name__ == "__main__":
    main()
