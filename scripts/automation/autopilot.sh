#!/usr/bin/env bash
# Unattended driver for Arabic enrichment pass 2 (Gemma proposes, Claude reviews). Task Scheduler runs it every
# 30 minutes through autopilot.vbs; each run does whatever is due and exits, so a Claude usage limit or a reboot
# only delays the work until the next run after the limit resets.
#   1. keep Ollama up
#   2. keep one Gemma `propose` running, dictionary by dictionary (priority: Data & AI, Legal, Contracts, rest)
#   3. when proposals are ready, run a headless Claude review (scripts/automation/review_prompt.md)
#   4. commit and push everything to origin/enrichment-pass1
#   5. once every Gemma proposal exists: run the decision test (scripts/evaluate/decision_gemma.py, the Jev
#      fallback), push its report, and write logs/gpu-free.flag — the arabic-dialect-to-msa autorun waits for
#      that file before it starts its GPU experiments (the Claude review keeps going, it needs no GPU)
#   6. when every dictionary is reviewed: rebuild embeddings (needs `hf auth login`) and write logs/autopilot.done
# Log: logs/autopilot.log
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1
mkdir -p logs/decisions
LOG=logs/autopilot.log
PY=.venv/Scripts/python
BRANCH=enrichment-pass1
BATCHES=${BATCHES:-5}
PRIORITY="4cd164a7 0f465c61 89af196b"
OLLAMA="$(cygpath "$LOCALAPPDATA")/Programs/Ollama/ollama.exe"

log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

LOCK=logs/autopilot.lock
if ! mkdir "$LOCK" 2>/dev/null; then
    [ -n "$(find "$LOCK" -maxdepth 0 -mmin +360)" ] || exit 0  # previous run still going
    log "removing stale lock"
    rm -rf "$LOCK" && mkdir "$LOCK" || exit 1
fi
trap 'rm -rf "$LOCK"' EXIT
[ -f logs/autopilot.done ] && exit 0

push() {
    git add -A data/dictionaries scripts reports HANDOFF.md
    if ! git diff --cached --quiet; then
        git commit -q -m "Arabic pass 2: autopilot progress $(date '+%F %R')" \
            -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" >> "$LOG" 2>&1 || log "commit failed"
    fi
    git push -q origin "$BRANCH" >> "$LOG" 2>&1 || log "push failed (will retry next run)"
}

# 1. Ollama
if ! curl -s -m 5 localhost:11434/api/version > /dev/null; then
    log "starting ollama"
    powershell.exe -NoProfile -Command "Start-Process -WindowStyle Hidden '$(cygpath -w "$OLLAMA")' serve" > /dev/null 2>&1
    sleep 15
fi

# <ready> TAB <pending> TAB <id prefix>, one line per dictionary
STATE="$($PY scripts/enrich/arabic_pass.py ready 2>> "$LOG")" || { log "ready check failed"; exit 1; }
ordered() {  # dictionary prefixes, priority ones first
    for p in $PRIORITY; do echo "$p"; done
    echo "$STATE" | cut -f3 | grep -v -x -F -f <(printf '%s\n' $PRIORITY)
}
field() { echo "$STATE" | awk -F'\t' -v p="$1" -v f="$2" '$3 == p { print $f }'; }

# 2. Gemma proposals: one process at a time, next dictionary still missing proposals
propose_running() {
    powershell.exe -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" |
        Where-Object { \$_.CommandLine -like '*arabic_auto.py*propose*' }).Count" | tr -d '\r' | grep -qv '^0$'
}
MISSING=$(echo "$STATE" | awk -F'\t' '{ s += $2 - $1 } END { print s + 0 }')  # pending senses without proposals
if ! propose_running && [ "$MISSING" -gt 0 ]; then
    for p in $(ordered); do
        if [ "$(field "$p" 2)" -gt "$(field "$p" 1)" ]; then
            log "starting gemma propose for $p"
            powershell.exe -NoProfile -Command "Start-Process -WindowStyle Hidden -WorkingDirectory '$(cygpath -w "$ROOT")' \
                -RedirectStandardOutput 'logs\\propose-$p.log' -RedirectStandardError 'logs\\propose-$p.err' \
                '.venv\\Scripts\\python.exe' 'scripts\\enrich\\arabic_auto.py propose --dictionary $p --workers 4'" \
                >> "$LOG" 2>&1
            break
        fi
    done
fi

READY=$(echo "$STATE" | awk -F'\t' '{ s += $1 } END { print s + 0 }')
PENDING=$(echo "$STATE" | awk -F'\t' '{ s += $2 } END { print s + 0 }')
log "ready=$READY pending=$PENDING missing_proposals=$MISSING"

# 5. GPU phase over: decision test once, then hand the GPU to arabic-dialect-to-msa
if [ "$MISSING" -eq 0 ] && [ ! -f logs/gpu-free.flag ] && ! propose_running; then
    log "all Gemma proposals done; running the decision test"
    if $PY scripts/evaluate/decision_gemma.py --per-class 300 >> "$LOG" 2>&1; then
        push
        date '+%F %T' > logs/gpu-free.flag
        log "decision test pushed (reports/decision_gemma.md); wrote logs/gpu-free.flag for arabic-dialect-to-msa"
    else
        log "decision test failed; retrying next run"
    fi
fi

# 3. Claude review of ready proposals
if [ "$READY" -gt 0 ]; then
    CLAUDE="$(ls -d "$HOME"/.vscode/extensions/anthropic.claude-code-*-win32-x64/resources/native-binary/claude.exe \
        2>/dev/null | sort -V | tail -1)"
    if [ -z "$CLAUDE" ]; then
        log "claude.exe not found"
    else
        PROMPT="$(sed "s/{BATCHES}/$BATCHES/" scripts/automation/review_prompt.md)"
        OUT="$(timeout 4h "$CLAUDE" -p "$PROMPT" --model claude-opus-5-5 --permission-mode acceptEdits \
            --allowedTools "Bash(.venv/Scripts/python scripts/enrich/arabic_pass.py:*)" "Read" "Write" "Edit" \
            --output-format json 2>&1)"
        CODE=$?
        echo "$OUT" | tail -c 2000 > logs/claude-last.json
        if echo "$OUT" | grep -qiE 'usage limit|limit reached|hit your limit|rate.?limit|overloaded'; then
            log "claude limit/overload (exit $CODE); retrying next run"
        else
            log "claude review finished (exit $CODE): $(echo "$OUT" | grep -o '"result":"[^"]*' | head -c 300)"
        fi
    fi
fi

# 4. publish
push

# 6. finished?
if [ "$PENDING" -eq 0 ] && [ -f logs/gpu-free.flag ]; then
    if [ -f "$HOME/.cache/huggingface/token" ]; then
        log "all dictionaries done; rebuilding embeddings"
        $PY scripts/embeddings/build_embeddings.py build >> "$LOG" 2>&1 || { log "embeddings failed"; exit 1; }
    else
        log "all dictionaries done; embeddings skipped (no 'hf auth login')"
    fi
    touch logs/autopilot.done
    log "DONE"
fi
