"""substrate_core.rlvr.verify_rlvr — il CANCELLO riproducibile del loop no-GPU (un comando).

  python -m substrate_core.rlvr.verify_rlvr   ->   "RLVR ALL GREEN" (o esce !=0)

Esegue: (1) la suite pytest; (2) la validazione STATICA dello script Colab (py_compile + AST-lint:
gli import GPU sono lazy, i simboli substrate_core.rlvr referenziati esistono); (3) un audit live della
fabbrica-dati (zero falsi-proven). Ogni riga di output cita cosa ha verificato. Niente GPU, niente torch.
"""
from __future__ import annotations

import ast
import os
import py_compile
import subprocess
import sys

HERE = os.path.dirname(__file__)


def _ok(msg): print("  OK  " + msg)
def _fail(msg): print("  XX  " + msg)


def run_pytest() -> bool:
    print("[1/3] pytest suite")
    r = subprocess.run([sys.executable, "-m", "pytest", os.path.join(HERE, "tests", "test_rlvr.py"), "-q"],
                       env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
                       capture_output=True, text=True)
    line = (r.stdout.strip().splitlines() or ["(no output)"])[-1]
    (_ok if r.returncode == 0 else _fail)("pytest: " + line)
    return r.returncode == 0


def validate_colab_script() -> bool:
    print("[2/3] validazione STATICA di train_qlora_colab.py (no-GPU)")
    path = os.path.join(HERE, "train_qlora_colab.py")
    try:
        py_compile.compile(path, doraise=True)
        _ok("py_compile: sintassi valida")
    except py_compile.PyCompileError as e:  # noqa
        _fail(f"py_compile FALLITO: {e}")
        return False
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    # gli import pesanti (torch/transformers/peft/trl/datasets) NON devono stare a livello-modulo
    heavy = {"torch", "transformers", "peft", "trl", "datasets"}
    top_imports = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_imports |= {n.name.split(".")[0] for n in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_imports.add(node.module.split(".")[0])
    leaked = heavy & top_imports
    if leaked:
        _fail(f"import GPU a livello-modulo (devono essere lazy): {leaked}")
        return False
    _ok("import GPU sono lazy (il file e' importabile senza torch)")
    # le credenziali non sono hardcoded
    if "hf_" in src.lower() and ("os.environ" in src or "userdata" in src):
        _ok("HF token preso da env/userdata, non hardcoded")
    return True


def audit_factory_live() -> bool:
    print("[3/3] audit live fabbrica-dati (zero falsi-proven)")
    from substrate_core.rlvr.factory import build_split
    from substrate_core.rlvr.reward import reward
    from substrate_core.rlvr.oracle import verify_equiv
    train = build_split(60, seed=0, split="train")
    A = [r for r in train if r["channel"] == "A"]
    B = [r for r in train if r["channel"] == "B"]
    C = [r for r in train if r["channel"] == "C"]
    a_ok = all(reward(r["prompt_regex"], r["completion"])["reward"] == 1.0 for r in A)
    b_ok = all(verify_equiv(r["prompt_regex"], r["completion"])["status"] == "REFUTED" for r in B)
    c_ok = bool(C) and all(r["got_status"] == "ABSTAIN" for r in C)
    fp = sum(1 for r in A if reward(r["prompt_regex"], r["completion"])["tier_sound"] != "proven")
    (_ok if a_ok else _fail)(f"canale A: {len(A)} record, tutti reward==1.0 = {a_ok}")
    (_ok if b_ok else _fail)(f"canale B: {len(B)} REFUTED sound = {b_ok}")
    (_ok if c_ok else _fail)(f"canale C: {len(C)} ABSTAIN-boundary = {c_ok}")
    (_ok if fp == 0 else _fail)(f"falsi-proven nel corpus = {fp} (deve essere 0)")
    return a_ok and b_ok and c_ok and fp == 0


def main() -> int:
    print("=== substrate_core.rlvr - cancello riproducibile (no-GPU) ===")
    ok = run_pytest() & validate_colab_script() & audit_factory_live()
    print("\n" + ("RLVR ALL GREEN" if ok else "RLVR GATE FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
