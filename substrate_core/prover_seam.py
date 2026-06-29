"""substrate_core.prover_seam — l'UNICO canale dell'untrusted PROVER verso il kernel verifier.

Tesi (Arthur/Merlin): il kernel e' il VERIFIER fidato (Arthur/NP); il prover e' l'LLM/agente NON-FIDATO
(Merlin). Il prover puo' SOLO sottomettere un claim (+ hint di fatti/witness). NON puo': asserire un verdetto
o un assurance tier, importare il kernel, scrivere il grafo. Tutto cio' che il prover dice e' UNTRUSTED:
il seam STRIPPA ogni asserzione-di-verita' e ROUTA per verify(), dove il GATE RI-ESEGUE.

=> PROVER-INDEPENDENCE: il prover sceglie i FATTI (whitelist per-dominio), il kernel RI-ESEGUE e DECIDE. Un
CONFIRMED falso non e' coniabile per ASSERZIONE (verdetto/tier/budget strippati) ne' per HIJACK NAIVE del canale-
risultato (sandbox a nonce: print/os._exit di un falso RJSON falliscono). RESIDUI ONESTI (recon 2026-06-05):
  (1) il fuzzing black-box puo' mancare un punto-singolo nascosto -> un pass pyprop resta EMPIRICAL, mai 'proven';
  (2) FRAME-WALK (FONDAMENTALE, NON chiuso): un prover INTROSPETTIVO in-process puo' risalire i frame Python
      (sys._getframe -> f_locals) e recuperare nonce/fd del canale per coniare un CONFIRMED falso. NON e' chiuso da
      SUBSTRATE_SANDBOX_WRAP (ri-esegue lo stesso interprete) e non e' chiudibile finche' il verdetto dipende da
      subject/prop NON-FIDATI (il prover controlla anche l'ORACOLO). Difesa realistica: prover NON-introspettivo.
Cheatbench MISURA questi residui, non li assume zero. Il kernel vede solo un Claim, come da un umano o un cron.
"""
from __future__ import annotations

from typing import Optional

from .kernel import Claim, verify

# Chiavi-param con cui un prover potrebbe TENTARE di asserire verita' (verdetto/forza/copertura): RIMOSSE
# prima del gate. Il prover sceglie i FATTI-hint (dominio/target/lane/seed/trials), MAI la verita'.
_TRUTH_ASSERTING = {
    # verdetto / forza (il prover non conia ne' promuove)
    "assurance", "status", "verdict", "residual_risk", "coverage",
    "proven", "confirmed", "refuted", "executed", "harness_strength", "witness", "proof",
    # provenienza cross-dominio (R3): il prover non puo' FABBRICARE un legame witness-passing
    "input_from", "input_witness", "input_status",
    # ontologia (R1): il prover non puo' ASSERIRE un tipo/merge d'entita' (deve venire da un probe eseguito)
    "entity_type", "role", "label", "merge", "same_as", "cluster", "match_score",
}

# Parametri di BUDGET D'ESECUZIONE: il prover NON li sceglie. Un buco VERIFICATO (recon 2026-06-04) mostrava
# che trials=0 -> CONFIRMED falso e wall_s~0 -> REFUTED soppressa, perche' il prover pilotava QUANTO si testa
# (il seam strippava la verita' ASSERITA ma non il budget). Il prover sceglie COSA testare; il kernel sceglie
# QUANTO DURAMENTE -> questi vengono STRIPPATI qui (e comunque il gate applica un floor: difesa in profondita').
_RESOURCE_PARAMS = {"trials", "seed", "wall_s", "mem_mb", "timeout", "max_iters", "budget"}

# WHITELIST per-dominio (defense-in-depth, recon 2026-06-05): il denylist sopra lasciava passare al gate
# QUALSIASI chiave NON elencata come "fatto fidato". Qui ribaltiamo: per ogni dominio passano SOLO i fact-hint
# legittimi (verificati leggendo ogni gate); ogni altra chiave viene SCARTATA e registrata in audit. I param di
# BUDGET e di VERITA' restano comunque strippati dai due set sopra (prima linea), QUALUNQUE dominio.
_DOMAIN_WHITELIST = {
    "pyprop": {"contract"},
    "smt": {"property_smt2", "smt2", "timeout_ms"},   # tier formale: la FORMULA e' un fatto-hint; l'oracolo e' Z3
    "wasmprop": {"wat", "wasm_hex", "export", "property", "domain", "fuel"},  # esecutore WASM isolato; oracolo host-fidato
    "differential": {"impl_lang", "contract"},
    "entity_probe": {"probe", "a", "b", "cospend_inputs", "tx", "interface", "source", "candidate",
                     "features", "data_window", "calibrated_miss_rate", "context", "state_proof"},
    "replay": set(),   # il legame cross-dominio (input_witness/input_from) e' TRUTH-asserting -> mai dal prover
    "erc4626": {"gate", "result_key", "onchain", "rpc", "test"},
}


def submit(claim_dict: dict, *, key: Optional[bytes] = None, stamp: str = "") -> dict:
    """Sottomissione da un PROVER NON-FIDATO. Strippa ogni asserzione-di-verita' E ogni parametro-di-budget
    del prover, poi il kernel RI-ESEGUE col suo budget.

    Ritorna la busta-certificato firmata DAL KERNEL (l'unico token di verita'), piu' metadata d'audit
    `prover` FUORI dal contenuto firmato (non tocca content_hash/firma).
    """
    raw = dict(claim_dict.get("params") or {})
    domain = str(claim_dict.get("domain", ""))
    allowed = _DOMAIN_WHITELIST.get(domain, set())
    # WHITELIST: passano SOLO i fact-hint ammessi per il dominio dichiarato; tutto il resto e' scartato.
    params = {k: v for k, v in raw.items() if k in allowed}
    stripped_truth = sorted(set(raw) & _TRUTH_ASSERTING)
    stripped_budget = sorted(set(raw) & _RESOURCE_PARAMS)
    dropped_unknown = sorted(k for k in raw if k not in allowed
                             and k not in _TRUTH_ASSERTING and k not in _RESOURCE_PARAMS)

    claim = Claim(
        domain=domain,
        target=str(claim_dict.get("target", "")),
        kind=str(claim_dict.get("kind", "untrusted-prover-claim")),
        params=params,
    )
    env = verify(claim, key=key, stamp=stamp)   # il GATE decide; cio' che il prover sperava e' irrilevante
    env["prover"] = {"trusted": False, "stripped_assertions": stripped_truth,
                     "stripped_budget": stripped_budget,
                     "dropped_unknown": dropped_unknown}  # audit, fuori dal cert firmato
    return env
