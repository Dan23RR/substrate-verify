"""Acceptance oracle for FIX 10 ('sandbox-isolation-hook').

P0 closed the result-channel hijack, but the sandbox is still a GAS METER, not an OS boundary:
untrusted code runs with full user privileges. FIX 10 adds a PLUGGABLE executor hook so a deployment
can wrap the runner subprocess in real OS isolation (firejail / nsjail / a container) via the env var
SUBSTRATE_SANDBOX_WRAP, defaulting to none.

This test sets SUBSTRATE_SANDBOX_WRAP to a BENIGN no-op wrapper (a tiny python script that simply
re-invokes its argv via subprocess) and asserts run_pyprop still returns a CORRECT REFUTED and a
CORRECT CONFIRMED through the wrapper -- i.e. the hook is honored and transparent for a pass-through
wrapper. It also asserts the docstring documents the non-isolation caveat.

Pre-fix (today): sandbox.py ignores SUBSTRATE_SANDBOX_WRAP -> setting it changes nothing, so we cannot
prove the hook exists. We assert presence of the wrap mechanism by checking that a DELIBERATELY BROKEN
wrap makes the run fail to produce a framed result (RESOURCE_EXCEEDED/ABSTAIN). On today's code the
broken wrap is ignored and the run still succeeds -> mismatch -> this script exits non-zero.
Post-fix: the broken wrap is actually used -> no framed result -> assertion holds -> exit 0.
"""
import os
import sys
import json
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from substrate_core import sandbox
from substrate_core.sandbox import run_pyprop

EX = os.path.join(REPO, "examples")
WRAP_ENV = "SUBSTRATE_SANDBOX_WRAP"

failures = []


def expect(label, cond):
    print(f"  [{'ok' if cond else 'XX'}] {label}")
    if not cond:
        failures.append(label)


# A benign PASS-THROUGH wrapper: a python script that re-invokes whatever argv follows it.
# This stands in for 'firejail --quiet --net=none --private -- <cmd>' etc.: a command PREFIX that
# ultimately execs the real runner. subprocess (not os.execv) is used for Windows portability.
_tmp = tempfile.mkdtemp(prefix="fix10_")
_passthru = os.path.join(_tmp, "passthru_wrap.py")
with open(_passthru, "w", encoding="utf-8") as f:
    f.write("import sys, subprocess\n"
            "sys.exit(subprocess.run(sys.argv[1:]).returncode)\n")

# A DELIBERATELY BROKEN wrapper: exits 13 WITHOUT ever running the runner. If the hook is honored,
# the runner never executes, so no nonce-framed result is produced -> RESOURCE_EXCEEDED/ABSTAIN.
_broken = os.path.join(_tmp, "broken_wrap.py")
with open(_broken, "w", encoding="utf-8") as f:
    f.write("import sys\nsys.exit(13)\n")


def _quote(p):
    # Build a command STRING that the fix parses with shlex.split(posix=True) (the universal
    # convention for SUBSTRATE_SANDBOX_WRAP, matching 'firejail ... ' / 'nsjail ... --' / 'docker run ...').
    # Double-quote each token: under POSIX shlex this preserves Windows backslash paths AND spaces,
    # and is exactly how a real deployment would quote an executable path. Round-trips on both OSes.
    return " ".join('"%s"' % x for x in (sys.executable, p))


# Sanity: with NO wrap, behavior is the known-good baseline.
os.environ.pop(WRAP_ENV, None)
base_ref = run_pyprop(os.path.join(EX, "ex_buggy_sort.py"), 200, 0)
base_ok = run_pyprop(os.path.join(EX, "ex_abs.py"), 200, 0)
expect("baseline (no wrap): buggy_sort -> REFUTED", base_ref.get("status") == "REFUTED")
expect("baseline (no wrap): ex_abs -> CONFIRMED", base_ok.get("status") == "CONFIRMED")

# (1) PASS-THROUGH wrap honored and TRANSPARENT: correct verdicts still come back.
os.environ[WRAP_ENV] = _quote(_passthru)
try:
    w_ref = run_pyprop(os.path.join(EX, "ex_buggy_sort.py"), 200, 0)
    w_ok = run_pyprop(os.path.join(EX, "ex_abs.py"), 200, 0)
finally:
    os.environ.pop(WRAP_ENV, None)
expect("pass-through wrap: buggy_sort still -> REFUTED (hook transparent)", w_ref.get("status") == "REFUTED")
expect("pass-through wrap: ex_abs still -> CONFIRMED (hook transparent)", w_ok.get("status") == "CONFIRMED")
# the REFUTED witness must survive the wrap (the channel is intact through the prefix)
expect("pass-through wrap: REFUTED still carries an executed witness", "input" in w_ref)

# (2) BROKEN wrap PROVES the hook is actually used: runner never runs -> no framed result.
# On today's code the env var is ignored, so the run SUCCEEDS as REFUTED -> this assertion FAILS today.
os.environ[WRAP_ENV] = _quote(_broken)
try:
    w_broken = run_pyprop(os.path.join(EX, "ex_buggy_sort.py"), 200, 0)
finally:
    os.environ.pop(WRAP_ENV, None)
expect("broken wrap honored: no nonce-framed result -> RESOURCE_EXCEEDED/ABSTAIN (NOT a REFUTED)",
       w_broken.get("status") in ("RESOURCE_EXCEEDED", "ABSTAIN") and w_broken.get("status") != "REFUTED")

# (3) the module documents that it is NOT OS isolation (auditable safety caveat). Require the
# SPECIFIC new warning language (privilege + a concrete OS-isolation tool) so this is a true oracle
# for part (a): today's docstring mentions neither 'privileg' nor 'firejail' -> this fails pre-fix.
_doc = (sandbox.__doc__ or "").lower()
expect("sandbox docstring explicitly warns NOT OS isolation (privilege + concrete jailer named)",
       "privileg" in _doc and ("firejail" in _doc or "nsjail" in _doc or "os-level" in _doc))

# (4) the wrap env-var name is referenced in the module source (the hook exists in code).
import inspect
_src = inspect.getsource(sandbox)
expect("SUBSTRATE_SANDBOX_WRAP hook present in sandbox.py source", "SUBSTRATE_SANDBOX_WRAP" in _src)

print("FIX10 sandbox-wrap:", "ALL OK" if not failures else f"{len(failures)} FAILED -> {failures}")
sys.exit(1 if failures else 0)
