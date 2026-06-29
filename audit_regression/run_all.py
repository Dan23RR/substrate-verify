"""Acceptance gate for the audit fixes: green board (verify_all.py) + every assert-based oracle
(audit_regression/test_*.py). Exits non-zero if anything regresses. One command to trust the tree."""
import glob, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PY = sys.executable
env = dict(os.environ); env["PYTHONIOENCODING"] = "utf-8"

def run(label, args, cwd):
    p = subprocess.run([PY, *args], cwd=cwd, capture_output=True, text=True, env=env, timeout=600)
    ok = (p.returncode == 0)
    tail = (p.stdout or "").strip().splitlines()[-1:] or [""]
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}: {tail[0][:90]}")
    if not ok:
        for ln in (p.stdout or "").splitlines()[-6:]:
            print("        " + ln)
        err = (p.stderr or "").strip().splitlines()[-3:]
        for ln in err:
            print("        ! " + ln)
    return ok

print("=" * 70)
print("AUDIT ACCEPTANCE GATE")
print("=" * 70)
results = [run("green board (verify_all.py)", ["verify_all.py"], REPO)]
for t in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
    results.append(run(os.path.basename(t), [t], REPO))
print("=" * 70)
n_fail = results.count(False)
print("ALL ACCEPTANCE GREEN" if n_fail == 0 else f"{n_fail} ACCEPTANCE CHECK(S) FAILED")
sys.exit(1 if n_fail else 0)
