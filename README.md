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
- `reset_day.sh` — vacía el progreso del crawl de ayer, para que hoy se vuelva a comprobar cada barco.
- `progress.sh` — imprime "`<listos> <total>`" barcos crawleados hoy, para saber si hace falta otra pasada.
- `update.sh` — paso final: combina lo que haya en `sailings.jsonl` con el historial anterior y genera `Cruise Watch.html` + `cw_data.json` actualizado.

## Cómo se usa (lo hace Claude automáticamente)

Una tarea programada, cada día:
1. Clona este repositorio.
2. `reset_day.sh` una vez.
3. Llama a `crawl.py` varias veces seguidas (en tandas de ~30 min, porque una sola llamada no puede durar horas) hasta que `progress.sh` diga que los 162 barcos están listos (o hasta un máximo de intentos).
4. `update.sh` para fusionar los precios del día en el historial.
5. Sube (`git push`) el `cw_data.json` actualizado (y `sailings.jsonl`) a este repositorio, para que el día siguiente arranque desde ahí.
6. Le manda a Manuel el `Cruise Watch.html` recién generado, con un resumen de qué cruceros subieron o bajaron de precio ese día (la propia salida de `gen.py` imprime una línea `PRICE_CHANGES: ...` con el detalle).

No hace falta que Manuel toque nada de este repositorio directamente.
