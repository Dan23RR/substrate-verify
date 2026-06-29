"""substrate_core.domains.differential — STELE DI ROSETTA: equivalenza semantica TRANS-LINGUAGGIO (Sfida 2).

Un UNICO gen(rng) iniettato in DUE runtime: la ref Python e un'impl in un altro linguaggio (oggi JavaScript via
`node`). Output confrontati input-per-input. Una DIVERGENZA eseguita e' una PROVA di non-equivalenza
(REFUTED + l'input esatto che diverge + i due output). Nessuna divergenza su N input campionati -> equivalenza
EMPIRICA (regola-del-3): il tier ONESTO per "bit-identici fino a prova contraria empirica". E' l'oracolo per le
migrazioni legacy->moderno (COBOL/C++ -> Rust/Go): stesso input, due binari, stesso risultato? Il kernel adjudica.

Estende la tesi PIU' PROFONDA del kernel (ri-esecuzione + controesempio eseguito) attraverso il confine di
linguaggio, SENZA infra esterna. Riusa seam, gas-meter, contract-gate, lattice, export .scar.
"""
from __future__ import annotations

import os
import shutil

from ..kernel import Claim, Verdict, Status, Domain, register, PROVEN, EMPIRICAL
from ..sandbox import run_diff

TRIALS_FLOOR = 64
WALL_S_FLOOR, WALL_S_CEIL = 3.0, 30.0
MEM_MB_FLOOR, MEM_MB_CEIL = 128, 2048
SEED_SWEEP = (0, 1, 2)
_RUNTIME = {"javascript": "node", "js": "node", "node": "node"}   # estendibile: rust->target binary, c->a.out, ...


def gate(claim: Claim) -> Verdict:
    path = claim.target
    if not os.path.exists(path):
        return Verdict(Status.ABSTAIN, executed=False, reason=f"file non trovato: {path}")
    lang = str(claim.params.get("impl_lang", "javascript")).lower()
    exe = _RUNTIME.get(lang)
    node = shutil.which(exe) if exe else None
    if not node:
        return Verdict(Status.ABSTAIN, executed=False,
                       reason=f"runtime '{lang}' non disponibile (manca '{exe}') -> equivalenza non adjudicabile")

    trials = max(int(claim.params.get("trials", 256)), TRIALS_FLOOR)   # il kernel fissa il floor, non il prover
    wall_s = min(max(float(claim.params.get("wall_s", 10.0)), WALL_S_FLOOR), WALL_S_CEIL)
    mem_mb = min(max(int(claim.params.get("mem_mb", 1024)), MEM_MB_FLOOR), MEM_MB_CEIL)
    contract = claim.params.get("contract", "")

    checked_total = 0
    for sd in SEED_SWEEP:
        res = run_diff(path, trials, sd, node=node, wall_s=wall_s, mem_mb=mem_mb, contract=contract)
        st = res.get("status")

        if st == "CONTRACT_VIOLATION":
            return Verdict(Status.ABSTAIN, executed=True,
                           reason=f"CONTRACT-GATE: {res.get('reason')} -> rigettato senza spendere il budget",
                           coverage={"contract_violation": True, "contract": res.get("contract")})
        if st == "RESOURCE_EXCEEDED":
            return Verdict(Status.ABSTAIN, executed=True, reason=f"budget di RISORSE superato ({res.get('reason')})",
                           coverage={"resource_guard": True, "wall_s": wall_s})
        if st == "ABSTAIN":
            return Verdict(Status.ABSTAIN, executed=True, reason=res.get("reason", "ABSTAIN"))
        if st == "REFUTED":
            i = res["trial"]
            return Verdict(Status.REFUTED, executed=True,
                           reason=f"DIVERGENZA trans-linguaggio al trial {i} (seed {sd}): Python e {lang} NON sono equivalenti",
                           witness={"input": res["input"], "output_ref(python)": res["output_ref"],
                                    f"output_impl({lang})": res["output_impl"], "trial": i, "seed": sd},
                           reproduce=f"ref(input) != impl_{lang}(input) sull'input mostrato",
                           assurance=PROVEN,
                           coverage={"method": f"differential-fuzz (python vs {lang})", "divergence_at_trial": i, "seed": sd})
        checked_total += int(res.get("checked", trials))

    if checked_total < TRIALS_FLOOR:
        return Verdict(Status.ABSTAIN, executed=True,
                       reason=f"evidenza INSUFFICIENTE: {checked_total} input < floor {TRIALS_FLOOR}")
    resid = 3.0 / checked_total
    return Verdict(Status.CONFIRMED, executed=True,
                   reason=f"NESSUNA divergenza in {checked_total} input su {len(SEED_SWEEP)} seed: equivalenza EMPIRICA python<->{lang}",
                   witness={"inputs_checked": checked_total, "ref_lang": "python", "impl_lang": lang, "seeds": list(SEED_SWEEP)},
                   reproduce=f"seed-sweep {list(SEED_SWEEP)}; ref(x)==impl_{lang}(x) per ogni input campionato",
                   assurance=EMPIRICAL, residual_risk=resid,
                   coverage={"method": f"differential-fuzz (python vs {lang})", "inputs": checked_total, "exhaustive": False},
                   assurance_caveat=("equivalenza EMPIRICA (regola-del-3): bit-identici sugli input campionati, NON prova "
                                     "esaustiva; SOTTOSTIMA se gen() non copre lo spazio di divergenza"))


def claim_templates(target: str):
    return [Claim(domain="differential", target=target, kind="equivalence",
                  params={"impl_lang": "javascript", "trials": 256})]


DIFFERENTIAL = Domain(
    name="differential", gate=gate, claim_templates=claim_templates,
    describe="Equivalenza semantica trans-linguaggio: stesso gen, due runtime, output confrontati -> REFUTED+divergenza | CONFIRMED(empirical) | ABSTAIN")
register(DIFFERENTIAL)
