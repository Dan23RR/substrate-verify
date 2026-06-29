"""Oracle for the CLI enterprise surface: the framework is usable end-to-end from the command line.
Invokes the real CLI (python -m substrate_core.cli) for domains / conformance / prove-smt and checks behavior."""
import os, sys, subprocess, tempfile
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import substrate_core as sc
env = dict(os.environ); env["PYTHONIOENCODING"] = "utf-8"; env["PYTHONPATH"] = REPO + os.pathsep + env.get("PYTHONPATH", "")
fails = []


def cli(*args, timeout=120):
    return subprocess.run([sys.executable, "-m", "substrate_core.cli", *args], cwd=REPO,
                          capture_output=True, text=True, env=env, timeout=timeout)

# domains: lists the registered domains incl. the new tiers
r = cli("domains")
if r.returncode != 0 or "pyprop" not in r.stdout:
    fails.append(f"`substrate domains` failed: {r.stdout[:200]}{r.stderr[:200]}")
if "smt" in sc.REGISTRY and "smt" not in r.stdout:
    fails.append("`domains` did not list the smt tier")
if "wasmprop" in sc.REGISTRY and "wasmprop" not in r.stdout:
    fails.append("`domains` did not list the wasmprop tier")

# conformance: the SPEC golden vectors self-check from the CLI -> CONFORMANT, exit 0
r = cli("conformance")
if r.returncode != 0 or "CONFORMANT" not in r.stdout or "NON-CONFORMANT" in r.stdout:
    fails.append(f"`substrate conformance` not CONFORMANT: {r.stdout[:200]}")

# prove-smt: the formal tier from the CLI (true forall property -> PROVEN)
if "smt" in sc.REGISTRY:
    d = tempfile.mkdtemp(prefix="cli_")
    f = os.path.join(d, "p.smt2")
    open(f, "w", encoding="utf-8").write("(declare-const x (_ BitVec 8))(assert (= (bvadd x #x00) x))")
    r = cli("prove-smt", f)
    if r.returncode != 0 or "PROVEN" not in r.stdout:
        fails.append(f"`substrate prove-smt` (true forall) should print PROVEN: {r.stdout[:200]}{r.stderr[:200]}")

if fails:
    print("FAIL test_cli_surface:"); [print("  -", x) for x in fails]; sys.exit(1)
print("PASS test_cli_surface: CLI exposes domains + conformance (CONFORMANT) + prove-smt (PROVEN) end-to-end")
