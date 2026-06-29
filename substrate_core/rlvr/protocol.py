"""substrate_core.rlvr.protocol — il PROTOCOLLO DI CONFRONTO pre-registrato (disciplina, anti p-hacking).

Congela PRIMA di addestrare: bracci, metrica primaria, soglia di morte, baseline onesto. Il dict di config
e' hash-congelato (content_hash sul canonical_json); ogni numero successivo cita questo hash. Spostare la
soglia DOPO aver visto i numeri = p-hacking = vietato.

Il confronto NON e' "organismo vs niente": e' WITNESS-CONDITIONED DPO vs CONTROLLO RLVR-binario, a PARI
seed/dataset/budget/oracolo. Se il delta < soglia -> NON muore il controllo, muore la TESI (morte pulita).
"""
from __future__ import annotations

from typing import Any, Dict

from substrate_core.kernel import content_hash, Certificate, Claim, Verdict, Status, canonical_json

DEATH_THRESHOLD_PP = 5.0   # delta(B - A) in punti percentuali, su >=3 seed

PROTOCOL: Dict[str, Any] = {
    "version": "rlvr-protocol-0.1.0",
    "domain": "regex_equiv",
    "task": "simplify(R_bloated) -> R' equivalente e piu' semplice (AST)",
    "brackets": {
        "A_control": {
            "name": "CONTROLLO RLVR-binario (SFT/RFT)",
            "reward": "SFT sui PROVEN (canale A, tier=empirical) + casi ABSTAIN (canale C)",
            "uses": "baseline forte; nessuna preferenza, nessun witness",
        },
        "B_plain_dpo": {
            "name": "DPO senza witness (ABLAZIONE)",
            "reward": "DPO sulle coppie; rejected SENZA la distinguishing_string",
            "uses": "il controllo APPAIATO per isolare il witness (stesso algoritmo/dati/budget di B_witness)",
        },
        "B_witness_dpo": {
            "name": "Witness-conditioned DPO (LA TESI)",
            "reward": "stesse coppie DPO MA con la distinguishing_string ESEGUITA iniettata nel rejected",
            "uses": "consuma il 'perche' del REFUTED (crepa #4) + coppie di calibrazione ABSTAIN",
        },
    },
    "shared": {"seed_set": [0, 1, 2], "same_dataset": True, "same_budget_steps": True,
               "same_base_model": "Qwen-2.5-Coder-1.5B (4-bit QLoRA)", "same_oracle": "regex_equiv"},
    "primary_metric": "solve_rate_genuino (evaluator.evaluate)",
    "secondary_metrics": ["false_proven_count (VINCOLO DURO == 0)", "abstain_recall", "risk_coverage.aurc"],
    "holdout": "factory.build_split(split='holdout') con REGOLE DISGIUNTE da train (anti-overfit, crepa #5)",
    "death_threshold_pp": DEATH_THRESHOLD_PP,
    "primary_test": ("EFFETTO-WITNESS PURO = media_seed(solve_rate(B_witness) - solve_rate(B_plain)). Isola la "
                     "SOLA variabile witness (stesso algoritmo/dati/budget). A_control vs B = SFT-vs-DPO, confound."),
    "kill_rule": ("Se media_seed(solve_rate(B_witness) - solve_rate(B_plain)) < death_threshold_pp E "
                  "B_witness non migliora abstain_recall/aurc in modo distinguibile, con false_proven==0 ovunque "
                  "-> TESI FALSIFICATA (per questo dominio). Morte pulita."),
    "pre_gate_zero_gpu": "pregate.score_pregate: se pass@1(base) < 0.05 -> progetto falsificato a costo zero.",
    "retired_claims": [
        "'l'intelligenza si somma via cert-algebra' (compose_and compone VERDETTI, non CAPACITA' — category-error)",
        "'addestrare contro un verificatore sound batte l'RLVR' come dato di fatto (e' cio' che il protocollo TESTA)",
        "pilastri 5-6 dell'Organismo (self-play, distill-merge): vaporware finche' non costruiti+falsificati",
    ],
    "honest_residuals": [
        "il reward di QUALITA' (ast_nodes) e' EMPIRICAL non sound: la soundness copre 'e' equivalente?' non 'e' un buon rewrite?'",
        "witness-conditioning e' un proxy testuale: da MISURARE al gate, non assunto",
        "ABSTAIN-boundary calibrato solo sui casi C INIETTATI (il generatore non li produce)",
    ],
}


def protocol_hash() -> str:
    """Hash congelato del protocollo (content_hash del kernel su un certificato che lo incapsula)."""
    cert = Certificate(
        claim=Claim(domain="rlvr_protocol", target=PROTOCOL["version"], kind="preregistration",
                    params=PROTOCOL),
        verdict=Verdict(Status.ABSTAIN, executed=False, reason="preregistration, non un verdetto"),
        engine="substrate_core.rlvr.protocol")
    return content_hash(cert)


def freeze() -> Dict[str, Any]:
    return {"protocol": PROTOCOL, "hash": protocol_hash(),
            "canonical_len": len(canonical_json(Certificate(
                claim=Claim("rlvr_protocol", PROTOCOL["version"], "preregistration", PROTOCOL),
                verdict=Verdict(Status.ABSTAIN, executed=False), engine="substrate_core.rlvr.protocol")))}


if __name__ == "__main__":
    import json
    fr = freeze()
    print("PROTOCOL HASH (congelato):", fr["hash"])
    print("death_threshold_pp:", PROTOCOL["death_threshold_pp"])
    print(json.dumps(PROTOCOL["retired_claims"], ensure_ascii=False, indent=1))
