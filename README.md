# Cruise Planner — datos y automatización

Repositorio de soporte para el dashboard **CRUISE - PLANNER** de Manuel. No es una app —
es solo el lugar donde Claude guarda, entre una ejecución diaria y la siguiente, los
scripts del crawl de icruise.com y el historial acumulado de precios de cada crucero.

## Archivos

- `ships.json` — lista estática de los 162 barcos/navieras que se rastrean (no cambia casi nunca).
- `crawl.py` — vuelve a leer los precios actuales de icruise.com para cada barco (tarda ~horas, con pausas para no saturar la web).
- `sailings.jsonl` — resultado crudo de la última pasada de `crawl.py` (una fila por salida de crucero).
- `cid2gid.json`, `details_full.jsonl`, `ship_specs.json` — datos de itinerario día a día y specs de los barcos, sacados una sola vez (casi no cambian, no se vuelven a crawlear a diario).
- `template.html` — la plantilla HTML/CSS/JS del dashboard.
- `gen.py` — combina todo lo anterior y genera el archivo final `Cruise Watch.html`. Fusiona el precio del día con el historial anterior (`cw_data.json`): si el precio no cambió, no agrega nada nuevo; si cambió, añade una entrada con la fecha.
- `cw_data.json` — el "estado" acumulado: todos los cruceros con su historial completo de precios hasta hoy. Esto es lo que hace que el historial no se pierda entre ejecuciones.
- `update.sh` — script que encadena todo lo anterior para una actualización diaria.

## Cómo se usa (lo hace Claude automáticamente)

Una tarea programada clona este repositorio cada día, corre `update.sh`, y luego:
1. Sube (`git push`) el `cw_data.json` actualizado a este repositorio, para que el día siguiente arranque desde ahí.
2. Le manda a Manuel el `Cruise Watch.html` recién generado, con un resumen de qué cruceros subieron o bajaron de precio ese día.

No hace falta que Manuel toque nada de este repositorio directamente.
