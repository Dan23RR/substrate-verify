"""substrate_core.sandbox — esecuzione RESOURCE-BOUNDED di codice non-fidato (il 'GAS METER').

NON e' il TCB: kernel.py resta PURO (nessun subprocess nel TCB di adjudicazione). Qui si isola l'ESECUZIONE
in un SUBPROCESSO con limiti di TEMPO (timeout) e MEMORIA (RLIMIT su POSIX). Un prover caotico
(`while True` / `[1]*10**10`) fa morire il FIGLIO, mai il kernel -> ABSTAIN(resource-exceeded), non un crash.

Architettura (coerente col firewall): il kernel adjudica; il sandbox esegue; il certificato e' l'unico output.

⚠️ AVVERTENZA DI SICUREZZA — questo NON e' un confine di isolamento del SISTEMA OPERATIVO. E' un gas-meter
(tempo/memoria) + isolamento del CANALE-RISULTATO (nonce) che CHIUDE il result-channel hijack NAIVE (un harness
che stampa un falso RJSON e/o os._exit). Il codice non-fidato gira comunque coi PRIVILEGI PIENI dell'utente
(legge/scrive file, apre socket); su Windows RLIMIT e' un no-op (resta solo il timeout).

RESIDUO FONDAMENTALE (recon 2026-06-05, NON chiuso — onesto): un attaccante IN-PROCESS che conosce l'implementazione
puo' risalire i frame Python (sys._getframe -> f_locals di main()) per recuperare il nonce e il fd del canale e
coniare un CONFIRMED falso. SUBSTRATE_SANDBOX_WRAP (firejail/nsjail/container) isola l'HOST (fs/rete/privilegi) ma
NON questo: ri-esegue lo STESSO interprete dove nonce/fd sono frame-locals. Chiuderlo davvero richiederebbe emettere
il verdetto da un processo che NON esegue codice non-fidato — irraggiungibile finche' il verdetto dipende da
subject/prop NON-FIDATI (il prover controlla anche l'ORACOLO). Modello di minaccia realisticamente difeso: prover
LLM/euristico NON-introspettivo. SUBSTRATE_SANDBOX_WRAP resta utile per l'isolamento dell'HOST (host-escape).
"""
from __future__ import annotations

import json
import os
import secrets
import shlex
import subprocess
import sys


def _wrap_prefix():
    """Prefisso-comando per l'ISOLAMENTO OS-LEVEL pluggable (firejail/nsjail/container). Vuoto = nessun wrapping.
    L'argv del runner diventa [*prefix, python, -m, runner, ...] -> un deployment puo' confinare il subprocesso."""
    w = (os.environ.get("SUBSTRATE_SANDBOX_WRAP") or "").strip()
    return shlex.split(w, posix=True) if w else []


def _parse_framed(p, nonce: str) -> dict:
    """Estrae il risultato FIDATO incorniciato col nonce del kernel ("RJSN<nonce>{json}"). Tutto cio' che il
    codice non-fidato puo' aver scritto su stdout (incluso un fake "RJSON{...}") NON porta il nonce -> ignorato.
    Nessun frame valido -> il figlio e' morto / non ha prodotto nulla -> budget superato."""
    out = p.stdout or ""
    marker = "RJSN" + nonce
    idx = out.find(marker)
    if idx < 0:
        return {"status": "RESOURCE_EXCEEDED",
                "reason": f"nessun risultato firmato dal runner (exit {p.returncode}; memory bomb / OOM / hijack tentato?)"}
    try:
        return json.loads(out[idx + len(marker):])
    except Exception:  # noqa
        return {"status": "ABSTAIN", "reason": "output del sandbox non parsabile"}


def run_pyprop(target_path: str, trials: int, seed: int, *, wall_s: float = 10.0, mem_mb: int = 1024,
               edge_probe: bool = True, contract: str = "") -> dict:
    """Esegue la valutazione pyprop in un subprocesso bounded. Ritorna il dict-risultato
    ({status: REFUTED|CONFIRMED|ABSTAIN|RESOURCE_EXCEEDED, ...}). Mai un'eccezione verso il kernel."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../substrate_core (repo)
    env = dict(os.environ)
    env["PYTHONPATH"] = repo_root + os.pathsep + env.get("PYTHONPATH", "")
    nonce = secrets.token_hex(16)            # canale-risultato non-falsificabile: solo il runner FIDATO lo conosce
    env["SUBSTRATE_RJSON_NONCE"] = nonce
    try:
        p = subprocess.run(
            [*_wrap_prefix(), sys.executable, "-m", "substrate_core._pyprop_runner",
             target_path, str(int(trials)), str(int(seed)), str(int(mem_mb)), str(1 if edge_probe else 0),
             str(contract or "")],
            capture_output=True, text=True, timeout=wall_s, env=env,
        )
    except subprocess.TimeoutExpired:
        return {"status": "RESOURCE_EXCEEDED", "reason": f"timeout {wall_s}s superato (loop non terminante?)"}
    except Exception as e:  # noqa
        return {"status": "ABSTAIN", "reason": f"sandbox non avviabile: {type(e).__name__}: {e}"}

    return _parse_framed(p, nonce)


def run_diff(target_path: str, trials: int, seed: int, *, node: str, wall_s: float = 10.0, mem_mb: int = 1024,
             contract: str = "") -> dict:
    """Esegue il FUZZING DIFFERENZIALE trans-linguaggio (Python ref vs impl via `node`) in un subprocesso bounded.
    Il padre lo bounda con timeout (gas-meter); il runner spawna a sua volta `node` sugli stessi input."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ)
    env["PYTHONPATH"] = repo_root + os.pathsep + env.get("PYTHONPATH", "")
    nonce = secrets.token_hex(16)            # stesso isolamento-canale del run_pyprop (codice ref non-fidato)
    env["SUBSTRATE_RJSON_NONCE"] = nonce
    try:
        p = subprocess.run(
            [*_wrap_prefix(), sys.executable, "-m", "substrate_core._diff_runner",
             target_path, str(int(trials)), str(int(seed)), str(int(mem_mb)), str(node), str(contract or ""),
             str(float(wall_s))],
            capture_output=True, text=True, timeout=wall_s + 4, env=env,
        )
    except subprocess.TimeoutExpired:
        return {"status": "RESOURCE_EXCEEDED", "reason": f"timeout {wall_s}s superato (impl non terminante?)"}
    except Exception as e:  # noqa
        return {"status": "ABSTAIN", "reason": f"sandbox-diff non avviabile: {type(e).__name__}: {e}"}
    return _parse_framed(p, nonce)


def python_wasm_path():
    """Percorso del python.wasm (wasm32-wasi). Env SUBSTRATE_PYTHON_WASM, altrimenti la cache ~/.substrate_wasi/."""
    return (os.environ.get("SUBSTRATE_PYTHON_WASM")
            or os.path.join(os.path.expanduser("~"), ".substrate_wasi", "python.wasm"))


def run_pyprop_wasi(target_path: str, trials: int, seed: int, *, wall_s: float = 10.0, mem_mb: int = 1024,
                    edge_probe: bool = True, contract: str = "") -> dict:
    """Esegue pyprop nel RECINTO FISICO WASI: un guest python.wasm (wasm32-wasi) via wasmtime, default-deny su
    fs/rete, env vuoto. Il codice non-fidato NON puo' raggiungere il kernel/nonce dell'host (memoria WASM separata):
    frame-walk-verso-il-kernel e host-escape neutralizzati. isolated=True nel risultato. Mai un'eccezione -> dict.
    (Il subprocesso e' boundato dal timeout = gas-meter wall-clock; +startup di CPython-wasm.)"""
    wasm = python_wasm_path()
    if not os.path.exists(wasm):
        return {"status": "ABSTAIN", "reason": "python.wasm assente (esecutore WASI non disponibile; vedi SPEC)",
                "isolated": False}
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ)
    env["PYTHONPATH"] = repo_root + os.pathsep + env.get("PYTHONPATH", "")
    nonce = secrets.token_hex(16)
    env["SUBSTRATE_RJSON_NONCE"] = nonce
    try:
        p = subprocess.run(
            [sys.executable, "-m", "substrate_core._wasi_host",
             target_path, str(int(trials)), str(int(seed)), "1" if edge_probe else "0", wasm],
            capture_output=True, text=True, timeout=wall_s + 25, env=env,   # +25: startup CPython-wasm
        )
    except subprocess.TimeoutExpired:
        return {"status": "RESOURCE_EXCEEDED", "reason": "timeout (guest WASI non terminante?)", "isolated": True}
    except Exception as e:  # noqa
        return {"status": "ABSTAIN", "reason": f"wasi-sandbox non avviabile: {type(e).__name__}: {e}", "isolated": False}
    return _parse_framed(p, nonce)
