#!/usr/bin/env bash
# prepublish_check.sh - the GATE. Run from the repo root BEFORE `git init` / first push.
#   bash scripts/prepublish_check.sh
# Exits non-zero if any check fails. Mechanizes PUBLISH_CHECKLIST.md steps 2-4.
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
note() { printf '  %-6s %s\n' "$1" "$2"; }
section() { printf '\n=== %s ===\n' "$1"; }

# Files that legitimately contain key-shaped strings that are NOT secrets: the regex benchmark
# corpus (detector patterns), TweetNaCl (public constants), signed certs (public keys only), the
# public eth_getProof fixture, this script, the gitleaks config, and the checklist (which spells
# the forbidden strings out on purpose).
ALLOW='github-regexp\.csv|nacl\.min\.js|\.scar$|eth_proof_fixture\.json|\.gitleaks\.toml|prepublish_check\.sh|PUBLISH_CHECKLIST\.md'

section "1. Secrets: high-signal patterns (corpus + public test vectors allowlisted)"
SECRETS=$(grep -rInE \
  -e 'ghp_[A-Za-z0-9]{20,}' -e 'github_pat_[A-Za-z0-9_]{20,}' \
  -e 'sk-[A-Za-z0-9]{20,}' -e 'gsk_[A-Za-z0-9]{20,}' -e 're_[A-Za-z0-9]{20,}' \
  -e 'AKIA[0-9A-Z]{16}' \
  -e '(alchemy|infura)\.(com|io)/v[23]/[A-Za-z0-9_-]{20,}' \
  -e 'BEGIN [A-Z ]*PRIVATE KEY' \
  --exclude-dir='.git' --exclude-dir='__pycache__' \
  . 2>/dev/null | grep -vE "$ALLOW")
if [ -n "$SECRETS" ]; then echo "$SECRETS"; note FAIL "potential secret(s) above"; fail=1; else note OK "no secret patterns"; fi

section "2. Sensitive FILES (keys / seeds / env / rpc)"
FILES=$(find . -type f \( -iname '*.pem' -o -iname '*.key' -o -iname '*.seed' \
  -o -iname '*signing_key*' -o -iname '*.env' -o -name '.rpc_url' -o -iname '*secret*' \) \
  2>/dev/null | grep -vE '\.env\.example|/__pycache__/')
if [ -n "$FILES" ]; then echo "$FILES"; note FAIL "sensitive file(s) above"; fail=1; else note OK "none (.env.example is fine)"; fi

section "3. No imported git history (must be a FRESH git init)"
NESTED=$(find . -type d -name .git 2>/dev/null | grep -v '^\./\.git$')
if [ -n "$NESTED" ]; then echo "$NESTED"; note FAIL "nested .git histories above - remove them"; fail=1; else note OK "no nested .git"; fi

section "4. Overclaims must stay absent (the 4 audited + forbidden additions)"
OC=0
XO="--exclude=PUBLISH_CHECKLIST.md --exclude=.gitleaks.toml --exclude=prepublish_check.sh --exclude-dir=.git --exclude-dir=__pycache__"
grep -rIn $XO -e '128 all green' -e '128 green' -e 'all 128 ' . 2>/dev/null && OC=1
grep -rIn $XO -e 'g1_exploit.json' . 2>/dev/null && OC=1
grep -rIn $XO -e 'cvc5' . 2>/dev/null && OC=1
grep -rInE $XO 'issuer_authenticated.{0,3}[:=][[:space:]]*True' . 2>/dev/null && OC=1
if [ "$OC" -eq 0 ]; then note OK "no overclaim strings"; else note FAIL "overclaim string(s) above"; fail=1; fi

section "5. Reproducible suite is green (0 FAIL; skips allowed)"
if python3 verify_all.py >/tmp/_pp_board.txt 2>&1; then
  P=$(grep -c '\[PASS\]' /tmp/_pp_board.txt); S=$(grep -c '\[SKIP\]' /tmp/_pp_board.txt); F=$(grep -c '\[FAIL\]' /tmp/_pp_board.txt)
  note OK "verify_all.py exit 0  (PASS=$P SKIP=$S FAIL=$F)"
else
  tail -3 /tmp/_pp_board.txt; note FAIL "verify_all.py returned non-zero"; fail=1
fi

section "6. Optional scanners (run if installed)"
if command -v gitleaks >/dev/null 2>&1; then
  if gitleaks detect --no-banner --redact -c .gitleaks.toml >/tmp/_gl.txt 2>&1; then
    note OK "gitleaks clean"
  else
    tail -5 /tmp/_gl.txt; note FAIL "gitleaks findings"; fail=1
  fi
else
  note SKIP "gitleaks not installed (recommended before push)"
fi

printf '\n========================================\n'
if [ "$fail" -eq 0 ]; then echo "GATE PASSED - safe to: git init && git add . && commit && push"; else echo "GATE FAILED - fix the above BEFORE pushing"; fi
printf '========================================\n'
exit "$fail"
