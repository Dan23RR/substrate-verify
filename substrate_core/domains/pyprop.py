"""substrate_core.domains.pyprop — dominio PYTHON-PROPERTY: proprieta' eseguibili su funzioni Python.

Dimostra che il kernel verification-native NON e' legato a Solidity. Lo STESSO principio
(claim falsificabile -> gate che esegue -> REFUTED/CONFIRMED/ABSTAIN -> certificato componibile)
si applica a qualsiasi funzione Python.

Il target e' un file Python che definisce:
    subject(x) -> y          la funzione sotto test
    prop(x, y) -> bool        l'invariante che deve valere (y == subject(x))
    gen(rng) -> x             come campionare un input casuale (rng = random.Random)

Il gate fuzza `trials` input:
  - QUALSIASI input viola prop  -> REFUTED + witness (l'input che falsifica) [sound: e' un vero controesempio]
  - tutti passano               -> CONFIRMED (confidenza-LIMITATA: N trial eseguiti, non prova esaustiva)
  - subject/prop sollevano      -> ABSTAIN (tipato, mai finto-verdetto)
"""
from __future__ import annotations

import importlib.util
import os
import random

from ..kernel import Claim, Verdict, Status, Domain, register, PROVEN, EMPIRICAL, NONE
from ..sandbox import run_pyprop, run_pyprop_wasi   # gas-meter in-process | RECINTO FISICO WASI (isolato)

# ESECUTORE ISOLATO (recon 2026-06-05): se attivo, pyprop gira in un guest python.wasm (wasm32-wasi) -> il codice
# non-fidato NON raggiunge il kernel/nonce/fd dell'HOST (memoria WASM separata) ne' l'OS -> frame-walk-VERSO-IL-KERNEL
# e host-escape NEUTRALIZZATI -> coverage.isolated=True. Scelta KERNEL-side (env, NON un param del prover che potrebbe
# fingere l'isolamento). Il tier resta EMPIRICAL: il prover scrive ancora `prop` DENTRO il guest (oracle-control
# confinato al guest usa-e-getta; vedi SPEC). Default OFF (comportamento invariato).
WASI_EXECUTOR = (os.environ.get("SUBSTRATE_PYPROP_WASI") == "1")


def _load(path: str):
    spec = importlib.util.spec_from_file_location("subject_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod


# --- L0.5 RESOURCE-NORMALIZATION: il KERNEL fissa il budget d'esecuzione, NON il prover. -----------------
# Chiude un buco di prover-independence VERIFICATO (recon 2026-06-04): poiche' trials/wall_s/seed arrivavano da
# claim.params, un prover non-fidato poteva FABBRICARE un verdetto SENZA asserirlo:
#   * trials=0  -> 0 esecuzioni -> 0 controesempi -> CONFIRMED falso su un subject buggato;
#   * wall_s~0  -> timeout immediato -> una REFUTED reale mascherata da ABSTAIN(resource).
# Principio: il prover sceglie COSA testare (target+harness); il KERNEL sceglie QUANTO DURAMENTE. Il prover puo'
# solo RENDERE il test PIU' duro (piu' trial), mai sotto il floor; i seed li sceglie il kernel (no seed-fortunato).
TRIALS_FLOOR = 64                      # sotto questa soglia, "nessun controesempio" NON e' CONFIRMED -> ABSTAIN
WALL_S_FLOOR, WALL_S_CEIL = 2.0, 30.0  # un timeout piu' corto sopprimerebbe un controesempio; piu' lungo e' abuso
MEM_MB_FLOOR, MEM_MB_CEIL = 128, 2048
SEED_SWEEP = (0, 1, 2)                 # CONFIRMED solo se sopravvive a TUTTI i seed KERNEL-scelti
EDGE_PROBE = True                      # CO-FUZZER: il kernel inietta input-edge -> il prover non sceglie da solo
                                       # la distribuzione di test (chiude l'evasione-di-regione di gen()).


def _budget(claim: Claim) -> dict:
    """Il prover puo' alzare i trial (test piu' duro) ma non scendere sotto il floor; tempo/memoria clampati."""
    def _num(key, default, cast):
        try:
            return cast(claim.params.get(key, default))
        except Exception:  # noqa
            return default
    return {
        "trials": max(_num("trials", 500, int), TRIALS_FLOOR),
        "wall_s": min(max(_num("wall_s", 10.0, float), WALL_S_FLOOR), WALL_S_CEIL),
        "mem_mb": min(max(_num("mem_mb", 1024, int), MEM_MB_FLOOR), MEM_MB_CEIL),
    }


def gate(claim: Claim) -> Verdict:
    path = claim.target
    if not os.path.exists(path):
        return Verdict(Status.ABSTAIN, executed=False, reason=f"file non trovato: {path}")
    b = _budget(claim)

    # SEED-SWEEP: il kernel sceglie i seed e ne richiede il superamento di TUTTI. Un REFUTED da QUALSIASI seed
    # vince (short-circuit). Il GAS METER (subprocesso bounded) protegge ogni run: loop/bomba -> ABSTAIN, no crash.
    checked_total, last_hs = 0, {}
    _runner = run_pyprop_wasi if WASI_EXECUTOR else run_pyprop
    _iso = {"isolated": True} if WASI_EXECUTOR else {}
    for sd in SEED_SWEEP:
        res = _runner(path, b["trials"], sd, wall_s=b["wall_s"], mem_mb=b["mem_mb"], edge_probe=EDGE_PROBE,
                      contract=claim.params.get("contract", ""))
        st = res.get("status")

        if st == "CONTRACT_VIOLATION":
            # CONTRACT-GATE (Pilastro 1): il prover ha generato solo input fuori-contratto -> rigetto a basso costo.
            return Verdict(Status.ABSTAIN, executed=True,
                           reason=f"CONTRACT-GATE: {res.get('reason')} -> rigettato SENZA spendere il budget di fuzz",
                           coverage={"contract_violation": True, "contract": res.get("contract"), "invalid": res.get("invalid")})
        if st == "RESOURCE_EXCEEDED":
            return Verdict(Status.ABSTAIN, executed=True,
                           reason=f"budget di RISORSE superato ({res.get('reason')}) [seed {sd}] -> il prover caotico non crasha il kernel",
                           coverage={"resource_guard": True, "wall_s": b["wall_s"], "mem_mb": b["mem_mb"]})
        if st == "ABSTAIN":
            return Verdict(Status.ABSTAIN, executed=True, reason=res.get("reason", "ABSTAIN"),
                           witness={k: res[k] for k in ("trial", "seed") if k in res})
        if st == "REFUTED":
            i = res["trial"]
            # un controesempio ESEGUITO e' sound: e' una PROVA che il claim e' falso -> tier PROVEN
            return Verdict(Status.REFUTED, executed=True,
                           reason=f"controesempio ESEGUITO al trial {i} (seed {sd}) (claim FALSO)",
                           witness={"input": res["input"], "output": res["output"], "trial": i, "seed": sd},
                           reproduce=f"random.Random({sd}); avanza al trial {i}; subject(input) viola prop",
                           assurance=PROVEN, coverage={"method": "random-fuzz (sandboxed, seed-sweep)", "counterexample_at_trial": i, "seed": sd, **_iso})

        # CONFIRMED da questo seed: la meta-verifica harness (critica #2) e' gia' stata calcolata nel subprocesso
        hs = res.get("harness", {}) or {}
        if hs.get("survivors"):
            return Verdict(Status.ABSTAIN, executed=True,
                           reason="harness NON adeguato (vacuo): la prop non rifiuta nemmeno un output sbagliato -> CONFIRMED declassato",
                           witness={"surviving_mutants": hs["survivors"]},
                           reproduce="substrate_core.harness.score_pyprop_harness (nel sandbox)",
                           assurance=NONE, coverage={"harness_strength": hs})
        last_hs = hs
        checked_total += int(res.get("checked", b["trials"]))

    # Tutti i seed CONFIRMED. PROMUOVI la regola-del-3 a GATE: troppo poca evidenza NON e' CONFIRMED (anti-gaming).
    if checked_total < TRIALS_FLOOR:
        return Verdict(Status.ABSTAIN, executed=True,
                       reason=f"evidenza INSUFFICIENTE: {checked_total} campioni < floor {TRIALS_FLOOR} -> niente CONFIRMED",
                       coverage={"checked": checked_total, "trials_floor": TRIALS_FLOOR})
    resid = 3.0 / checked_total
    return Verdict(Status.CONFIRMED, executed=True,
                   reason=f"nessun controesempio in {checked_total} trial su {len(SEED_SWEEP)} seed KERNEL-scelti (empirico, sandboxed); harness adeguato",
                   witness={"trials_passed": checked_total, "seeds": list(SEED_SWEEP)},
                   reproduce=f"seed-sweep {list(SEED_SWEEP)} (kernel); {checked_total} trial; prop sempre vera",
                   assurance=EMPIRICAL,
                   coverage={"method": "random-fuzz (sandboxed, seed-sweep)", "trials": checked_total,
                             "exhaustive": False, "seeds": list(SEED_SWEEP), "harness_strength": last_hs, **_iso},
                   residual_risk=resid,
                   assurance_caveat="regola-del-3 (95% CI) sulla distribuzione di gen(); SOTTOSTIMA se blackbox/non-uniforme o se gen() non copre lo spazio")


def claim_templates(target: str):
    return [Claim(domain="pyprop", target=target, kind="invariant", params={"trials": 500, "seed": 0})]


PYPROP = Domain(
    name="pyprop",
    gate=gate,
    claim_templates=claim_templates,
    describe="Proprieta' eseguibili su funzioni Python: fuzz -> REFUTED+controesempio | CONFIRMED (N-trial) | ABSTAIN",
)
register(PYPROP)
