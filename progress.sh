#!/usr/bin/env bash
# Prints "<done> <total>" ships crawled so far today. Used by the calling agent to
# decide whether to run another crawl.py pass or move on to gen.py.
set -euo pipefail
cd "$(dirname "$0")"
python3 -c "
import json
done = len(json.load(open('state.json'))['done']) if __import__('os').path.exists('state.json') else 0
total = len(json.load(open('ships.json')))
print(done, total)
"
