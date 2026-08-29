#!/usr/bin/env bash
# Local pre-commit / CI parity check runner for MySmartHome.
#
# Runs, in order (mirrors .github/workflows/ci.yml):
#   1. py_compile of key Python modules + all tools/*.py + tests
#   2. secret scan (staged, blocking) + full-tree (--all, report-only)
#   3. git diff --check HEAD (whitespace / conflict markers)
#   4. line-ending policy check (committed content must be LF, per .gitattributes)
#   5. inline-JS syntax check (smarthouse_v8.html, tablet-panel.js, tablet.html)
#   6. pytest (live tests deselected by default)
#
# No secrets are required. Exits non-zero if any *blocking* check fails.
# The full-tree secret scan is report-only (it inspects gitignored runtime
# files that legitimately hold credentials) and never fails the run.

set -u
cd "$(dirname "$0")/.." || exit 2
ROOT="$(pwd)"
PY="${PYTHON:-python3}"
FAIL=0

section() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
ok()      { printf '  \033[32mOK\033[0m %s\n' "$1"; }
bad()     { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAIL=1; }
warn()    { printf '  \033[33m..\033[0m %s\n' "$1"; }

# --------------------------------------------------------------------------- #
section "1. Python compile (key modules)"
PY_TARGETS=(
    "project_secrets.py"
    "ha_ssh.py"
    "ev_common.py"
    "ev_best2h.py"
    "ev_day2h.py"
    "ev_night2h.py"
    "ev_query.py"
    "custom_components/miniapp_auth/__init__.py"
)
# All tools/*.py (secret_scan + energy_cost package).
while IFS= read -r f; do PY_TARGETS+=("$f"); done \
    < <(find tools -name '*.py' -not -path '*/__pycache__/*' 2>/dev/null)
# Include our own test files too.
while IFS= read -r f; do PY_TARGETS+=("$f"); done < <(find tests -name '*.py' 2>/dev/null)

for f in "${PY_TARGETS[@]}"; do
    if [ -f "$f" ]; then
        if "$PY" -m py_compile "$f" 2>/tmp/pycompile_err; then
            ok "$f"
        else
            bad "$f"
            sed 's/^/      /' /tmp/pycompile_err
        fi
    else
        warn "skip (missing): $f"
    fi
done

# --------------------------------------------------------------------------- #
section "2. Secret scan"
if [ -f tools/secret_scan.py ]; then
    if "$PY" tools/secret_scan.py; then
        ok "staged files clean"
    else
        bad "staged files contain possible secrets (blocking)"
    fi
    # Full-tree scan is report-only: gitignored runtime files may hold real
    # creds legitimately; we surface but never fail on them.
    if "$PY" tools/secret_scan.py --all; then
        ok "full tree clean"
    else
        warn "full-tree scan reported findings (report-only, not blocking)"
    fi
else
    warn "tools/secret_scan.py missing — skipping"
fi

# --------------------------------------------------------------------------- #
section "3. git diff --check (whitespace / conflict markers)"
if git rev-parse --verify HEAD >/dev/null 2>&1; then
    if git diff --check HEAD; then
        ok "no whitespace errors / conflict markers"
    else
        bad "git diff --check reported problems"
    fi
else
    warn "no HEAD commit — skipping diff check"
fi

# --------------------------------------------------------------------------- #
section "4. Line-ending policy (.gitattributes, LF)"
# Enforce `* text=auto eol=lf` for COMMITTED content without renormalizing this
# cycle: inspect the index side only. Working-tree CRLF (e.g. a Windows editor)
# is tolerated; committing CRLF is not.
if git rev-parse --verify HEAD >/dev/null 2>&1 || git ls-files >/dev/null 2>&1; then
    le_bad="$(git ls-files --eol | grep -E 'i/(crlf|mixed)' || true)"
    if [ -z "$le_bad" ]; then
        ok "all committed text files are LF"
    else
        bad "committed files violate LF policy:"
        printf '%s\n' "$le_bad" | sed 's/^/      /'
    fi
else
    warn "no git tree — skipping line-ending check"
fi

# --------------------------------------------------------------------------- #
section "5. Inline JS syntax check"
# Syntax-checks JS with node's vm.Script (compile only; nothing executes).
#  * .js/.mjs files are checked as-is.
#  * .html files: every inline (non-src) <script> block is extracted first.
# Prints one line per file:  "OK <f>" | "FAIL <f> <msg>" | "SKIP <f> ...".
JS_EXTRACT_CHECK='
const fs=require("fs"),vm=require("vm");
let failed=false;
for(const f of process.argv.slice(1)){
  if(!fs.existsSync(f)){console.log("SKIP "+f+" (missing)");continue;}
  const src=fs.readFileSync(f,"utf8");
  let body;
  if(/\.m?js$/i.test(f)){
    body=src;
  } else {
    const re=/<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
    let m; body="";
    while((m=re.exec(src))){ if(/\bsrc\s*=/i.test(m[1]))continue; body+=m[2]+"\n;\n"; }
    if(!body.trim()){console.log("SKIP "+f+" (no inline JS)");continue;}
  }
  try{ new vm.Script(body,{filename:f}); console.log("OK "+f); }
  catch(e){ console.log("FAIL "+f+" :: "+e.message); failed=true; }
}
process.exit(failed?1:0);
'
if command -v node >/dev/null 2>&1; then
    js_out="$(node -e "$JS_EXTRACT_CHECK" miniapp/smarthouse_v8.html tablet/tablet-panel.js tablet/tablet.html)"
    js_rc=$?
    while IFS= read -r line; do
        case "$line" in
            OK\ *)   ok "${line#OK }" ;;
            SKIP\ *) warn "${line#SKIP }" ;;
            FAIL\ *) bad "inline JS: ${line#FAIL }" ;;
            *)       [ -n "$line" ] && warn "$line" ;;
        esac
    done <<< "$js_out"
    [ "$js_rc" -ne 0 ] && FAIL=1
else
    warn "node not installed — skipping JS syntax check"
fi

# --------------------------------------------------------------------------- #
section "6. pytest"
if "$PY" -c "import pytest" 2>/dev/null; then
    if "$PY" -m pytest -q; then
        ok "pytest passed"
    else
        bad "pytest failed"
    fi
else
    warn "pytest not installed (pip install pytest) — skipping"
fi

# --------------------------------------------------------------------------- #
section "Result"
if [ "$FAIL" -eq 0 ]; then
    printf '\033[32mAll blocking checks passed.\033[0m\n'
else
    printf '\033[31mOne or more blocking checks failed.\033[0m\n'
fi
exit "$FAIL"
