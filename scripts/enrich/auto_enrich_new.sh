#!/bin/zsh
# Watch dictionaries that are still being extracted; as each one completes, run the Qwen draft for it.
# Usage: scripts/enrich/auto_enrich_new.sh NAME [NAME ...]   (names from extract_finance_media.py TARGETS)
set -u
cd "$(dirname "$0")/../.."
remaining=("$@")
while (( ${#remaining} )); do
  still=()
  for name in $remaining; do
    id=$(python3 -c "import sys; sys.path.insert(0, 'scripts/extract'); from extract_finance_media import TARGETS; print(TARGETS['$name'])" 2>/dev/null)
    export_file=data/dictionaries/exports/$id.json
    if python3 -c "import json,sys; sys.exit(json.load(open('$export_file')).get('status') != 'complete')" 2>/dev/null; then
      echo "== $(date '+%F %T') $name complete; generating Qwen drafts"
      .venv/bin/python -u scripts/enrich/enrich_dictionaries.py generate --dictionary "$id" --workers 8
    else
      still+=$name
    fi
  done
  remaining=($still)
  (( ${#remaining} )) && /bin/sleep 300
done
echo "== $(date '+%F %T') all watched dictionaries extracted and drafted"
