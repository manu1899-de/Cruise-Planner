#!/usr/bin/env bash
# Daily price-refresh for CRUISE - PLANNER.
# Run from inside the cloned repo directory. Expects TODAY=YYYY-MM-DD in the environment
# (the calling agent should pass today's real date).
#
# What it does:
#   1. Wipes the crawl's resume-state so every ship gets re-checked today (not skipped
#      as "already done" from a previous day).
#   2. Re-scrapes current prices for all ~162 ships from icruise.com (crawl.py). This is
#      the slow, polite part (anti-bot pauses) — budget a few hours for it.
#   3. Rebuilds the catalog with gen.py, merging today's prices into each cruise's price
#      history (cw_data.json) so only real price *changes* get logged — unchanged prices
#      don't bloat the file.
#   4. Prints a PRICE_CHANGES summary (also emitted by gen.py) so the calling agent can
#      report it to the user without re-deriving it.
set -euo pipefail
cd "$(dirname "$0")"

TODAY="${TODAY:-$(date -u +%Y-%m-%d)}"

echo "== wiping crawl resume-state so all ships are re-checked today =="
rm -f state.json log.txt
: > sailings.jsonl

echo "== re-crawling current prices from icruise.com (this takes a while, be patient) =="
# MAXSECS is a per-invocation deadline; crawl.py saves progress to state.json and can be
# re-run to resume where it left off, so loop until every ship is marked done.
PAUSE="${PAUSE:-15}" MAXSECS="${MAXSECS:-1800}"
attempt=0
while :; do
  attempt=$((attempt+1))
  echo "-- crawl.py attempt $attempt --"
  PAUSE="$PAUSE" MAXSECS="$MAXSECS" python3 crawl.py || true
  done_count=$(python3 -c "import json;print(len(json.load(open('state.json'))['done']))" 2>/dev/null || echo 0)
  total=$(python3 -c "import json;print(len(json.load(open('ships.json'))))")
  echo "progress: $done_count/$total ships done"
  if [ "$done_count" -ge "$total" ]; then break; fi
  if [ "$attempt" -ge 12 ]; then echo "giving up after $attempt attempts, proceeding with partial data"; break; fi
done

echo "== rebuilding catalog + merging price history =="
PREV_OUTPUT="$(pwd)/cw_data.json" OUT="$(pwd)/Cruise Watch.html" DATA_OUT="$(pwd)/cw_data.json" TODAY="$TODAY" python3 gen.py
