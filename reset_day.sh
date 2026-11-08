#!/usr/bin/env bash
# Call this ONCE at the start of each day's run, before the first crawl.py pass.
# Wipes the crawl's resume-state so every ship gets re-checked today (otherwise
# crawl.py would skip every ship as "already done" from a previous day).
set -euo pipefail
cd "$(dirname "$0")"
rm -f state.json log.txt
: > sailings.jsonl
echo "reset done: sailings.jsonl truncated, state.json removed"
