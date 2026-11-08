#!/usr/bin/env bash
# Final step of the daily refresh: rebuild the catalog from whatever is currently in
# sailings.jsonl, merging today's prices into each cruise's price history (cw_data.json)
# so only real price *changes* get logged. Run this AFTER crawl.py has made as much
# progress as it's going to make for the day (see reset_day.sh / progress.sh).
set -euo pipefail
cd "$(dirname "$0")"
TODAY="${TODAY:-$(date -u +%Y-%m-%d)}"
PREV_OUTPUT="$(pwd)/cw_data.json" OUT="$(pwd)/Cruise Watch.html" DATA_OUT="$(pwd)/cw_data.json" TODAY="$TODAY" python3 gen.py
