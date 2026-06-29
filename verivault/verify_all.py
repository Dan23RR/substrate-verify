#!/usr/bin/env python
"""
verify_all.py — UN comando per riprodurre TUTTO il green-board di VeriVault (contestabile / ri-eseguibile).

Gira: (A) gli eval/test Python del CORE (offline, self-contained) e (B) i forge-gate offline (se GATE_DIR + forge
presenti). Stampa un board e ritorna exit!=0 se QUALSIASI test con assert fallisce. Gli eval informativi
(death_gate, conformal_gate) stampano verdetti ONESTI (anche NO-GO) e non falliscono il build: il loro valore e' il
numero misurato, non un pass/fail. I gate-forge e i test con assert (test_*) sono i veri cancelli.

Uso:
  python verify_all.py
  GATE_DIR=/path/al/gate FORGE_BIN=/path/forge python verify_all.py    # override
"""
from __future__ import annotations
import os, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
_BUNDLED = os.path.join(HERE, "gate")                       # forge-gate self-contained dentro verivault/
_RESEARCH = os.path.normpath(os.path.join(HERE, "..", "research_substrate_capacity", "exp", "virgin", "gate"))
GATE = os.environ.get("GATE_DIR", _BUNDLED if os.path.isdir(_BUNDLED) else _RESEARCH)
os.environ["GATE_DIR"] = GATE   # i subtest eval/*.py ereditano il gate bundled -> green-board SELF-CONTAINED
FORGE = os.environ.get("FORGE_BIN", "forge")

# (A) Python: i test con ASSERT sono cancelli (falliscono il build); gli eval informativi girano per output onesto.
PY_ASSERT = ["eval/test_algebra.py", "eval/test_certificate.py", "eval/test_cascade.py",
             "eval/test_correlated_failure.py", "eval/test_numerical_oracle.py",
             "eval/test_substrate_agnostic.py", "eval/test_redteam_limits.py",
             "eval/test_product_flow.py", "eval/test_extractor.py",
             "eval/test_death_gate_runner.py", "eval/test_stage3.py",
             "eval/death_gate_w5v2.py", "eval/head_to_head.py"]
PY_INFO = ["eval/death_gate.py", "eval/conformal_gate.py"]
# (B) forge-gate offline (no-RPC): il moat eseguibile + composizione + fuzz-immunita.
GATES = ["LabeledBench", "CTokenGate", "GeneralGate", "RoundingGate", "RealSolmateGate",
         "CoupledGate", "OracleCoupledGate", "FuzzGate", "ThirdPartyGate"]


def _run(cmd, cwd=None, timeout=600):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception as e:  # noqa
        return False, str(e)


def main():
    results = []  # (name, ok|None)  None = skipped

    ok_imp, _ = _run([sys.executable, "-c", "import verivault"], cwd=HERE)
    results.append(("python -c 'import verivault'", ok_imp))

    for p in PY_ASSERT:
        ok, _ = _run([sys.executable, p], cwd=HERE)
        results.append((f"python {p}", ok))
    for p in PY_INFO:
        ok, _ = _run([sys.executable, p], cwd=HERE)
        results.append((f"python {p} (info)", ok))

    have_forge, _ = _run([FORGE, "--version"])
    if have_forge and os.path.isdir(GATE):
        for g in GATES:
            ok, _ = _run([FORGE, "test", "--match-path", f"test/{g}.t.sol"], cwd=GATE)
            results.append((f"forge {g}", ok))
    else:
        results.append((f"forge gates (GATE_DIR={GATE}, forge={have_forge})", None))

    print("=" * 64)
    print("VeriVault — verify_all (green-board riproducibile)")
    print("=" * 64)
    failed = 0
    for name, ok in results:
        tag = "PASS" if ok is True else ("SKIP" if ok is None else "FAIL")
        if ok is False:
            failed += 1
        print(f"  [{tag}] {name}")
    print("=" * 64)
    print("ALL GREEN" if failed == 0 else f"{failed} FAILED")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
