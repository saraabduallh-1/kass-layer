#!/usr/bin/env bash
# Keeps the arabic-dialect-to-msa benchmark (its src/autorun.py) moving while the user is away; autopilot.sh calls
# this every run. It uses no Claude unless a benchmark step gives up after its retries: then ONE headless Claude fix
# attempt per failed step, and once autorun has finished its pass it is restarted so the unfinished steps run again.
# Log lines go to kass-layer/logs/autopilot.log with a [dialect] prefix.
set -u
KASS="$(cd "$(dirname "$0")/../.." && pwd)"
DIALECT="$KASS/../arabic-dialect-to-msa"
[ -d "$DIALECT" ] || exit 0
DIALECT="$(cd "$DIALECT" && pwd)"
LOG="$KASS/logs/autopilot.log"
PY="$KASS/.venv/Scripts/python"
SEEN="$KASS/logs/dialect-fixed.txt"        # failed steps already handed to Claude
RESTART="$KASS/logs/dialect-restart.pending"
RLOG="$DIALECT/results/autorun.log"
LOCKF="$DIALECT/results/autorun.lock"
log() { echo "$(date '+%F %T') [dialect] $*" >> "$LOG"; }
[ -f "$RLOG" ] || exit 0
touch "$SEEN"

alive() { [ -f "$LOCKF" ] && [ -n "$(find "$LOCKF" -mmin -10)" ]; }  # autorun touches its lock every 2 min
# failed steps that are still not recorded as done in autorun_state.json
open_failures() {
    grep -a '!!! giving up on ' "$RLOG" | sed 's/.*!!! giving up on //; s/, continuing with the next step.*//' \
        | sort -u | "$PY" -c "import json, sys
from pathlib import Path
state = Path(sys.argv[1])
done = json.loads(state.read_text(encoding='utf-8')) if state.exists() else {}
for line in sys.stdin.read().splitlines():
    if line.strip() and line.strip() not in done:
        print(line.strip())" "$DIALECT/results/autorun_state.json"
}

STEP="$(open_failures | grep -v -x -F -f "$SEEN" | head -1)"
if [ -n "$STEP" ] && [ ! -f "$KASS/logs/review-stopped.flag" ]; then
    CLAUDE="$(ls -d "$HOME"/.vscode/extensions/anthropic.claude-code-*-win32-x64/resources/native-binary/claude.exe \
        2>/dev/null | sort -V | tail -1)"
    log "step '$STEP' gave up; asking Claude for one fix attempt"
    PROMPT="You are fixing an unattended benchmark while the user is away for days. The step '$STEP' of src/autorun.py
failed three times. Below is the end of results/autorun.log. Find the cause and make the smallest fix in src/ so the
step succeeds when autorun retries it. You may run quick checks with .venv/Scripts/python (seconds to a few minutes:
no full training or benchmark runs, no large downloads). Do not commit or push, do not edit data/ or results/, do
not ask questions. If it cannot be fixed in code (e.g. out of GPU memory), make the step lighter only if that keeps
the comparison fair, otherwise change nothing. End with one line: what you changed, or 'not fixable: <reason>'.

$(grep -a -n "" "$RLOG" | tail -120)"
    OUT="$(cd "$DIALECT" && timeout 45m "$CLAUDE" -p "$PROMPT" --model claude-opus-5-5 --permission-mode acceptEdits \
        --allowedTools "Read" "Edit" "Grep" "Glob" "Bash(.venv/Scripts/python:*)" --strict-mcp-config \
        --no-session-persistence --output-format json 2>&1)"
    echo "$OUT" > "$KASS/logs/claude-dialect-last.json"
    if echo "$OUT" | grep -q '"is_error":false'; then
        echo "$STEP" >> "$SEEN"
        touch "$RESTART"
        log "Claude fix attempt for '$STEP': $(echo "$OUT" | grep -o '"result":"[^"]*' | tail -c 300)"
    elif echo "$OUT" | grep -qi 'weekly'; then
        date '+%F %T' > "$KASS/logs/review-stopped.flag"
        log "claude WEEKLY limit reached: Claude work stopped (delete logs/review-stopped.flag to resume)"
    else
        log "Claude fix attempt for '$STEP' did not run (limit or error); retrying next run"
    fi
fi

# once autorun has finished its pass, rerun it so the fixed steps are retried (finished steps are skipped)
if [ -f "$RESTART" ] && ! alive && grep -aq "ALL DONE" "$RLOG"; then
    rm -f "$RESTART"
    log "restarting autorun to retry: $(open_failures | tr '\n' ';')"
    powershell.exe -NoProfile -Command "Start-Process -WorkingDirectory '$(cygpath -w "$DIALECT")' \
        '$(cygpath -w "$DIALECT")\\.venv\\Scripts\\pythonw.exe' 'src\\autorun.py'" >> "$LOG" 2>&1
fi
