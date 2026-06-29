"""Regression oracle for FIX 7 'docs-align': docs must match the post-fix code, honestly.
Asserts stale/overclaimed phrasing is gone and the honest qualifiers are present."""
import os, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return open(os.path.join(REPO, p), encoding="utf-8").read()


fails = []
readme = read("README.md")
if "signed (HMAC)" in readme:
    fails.append("README still claims certificates are 'signed (HMAC)' (code uses Ed25519)")
if "Ed25519" not in readme:
    fails.append("README should state Ed25519 signing")
if "16 checks" in readme:
    fails.append("README still cites the stale '16 checks' count")

seam = read("substrate_core/prover_seam.py")
if "nemmeno avversariale" in seam:
    fails.append("prover_seam still carries the UNQUALIFIED 'nemmeno avversariale ... CONFIRMED falso' absolute")
if "RESIDUI ONESTI" not in seam:
    fails.append("prover_seam should state the honest residuals (point-evasion EMPIRICAL, OS isolation)")

gha = read("substrate_core/github_adapter.py")
if "a falsi-positivi ZERO" in gha:
    fails.append("github_adapter title still says unqualified 'a falsi-positivi ZERO'")
if "falsi-ALLARME" not in gha or "falsi NEGATIVI" not in gha:
    fails.append("github_adapter should reframe to 'falsi-ALLARME' and disclose the false-NEGATIVE residual")

if fails:
    print("FAIL test_docs_align:"); [print("  -", f) for f in fails]; sys.exit(1)
print("PASS test_docs_align: docs match the post-fix code (Ed25519, honest prover-independence/guardian residuals)")
