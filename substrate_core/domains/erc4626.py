"""substrate_core.domains.erc4626 — dominio SOLIDITY/ERC-4626 via l'exec-gate forge di VeriVault.

Innesta il verticale validato (VeriVault) nel kernel generale: lo STESSO certificato a 3 vie,
ma il gate qui ESEGUE un exploit forge su un fork/harness. Claim = "il vault e' IMMUNE a donation/inflation".
  exploit eseguito (VULN)  -> REFUTED  (l'immunita' e' FALSA) + witness=profitto attaccante
  immunita' provata (IMMUNE)-> CONFIRMED + witness=prova
  fuori scope / no-forge    -> ABSTAIN
"""
from __future__ import annotations

import os
import sys

from ..kernel import Claim, Verdict, Status, Domain, register, PROOF, BOUNDED

# verivault e' un repo sibling: .../Startup/verivault (contiene il package `verivault`)
_VV_REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "verivault"))
if os.path.isdir(_VV_REPO) and _VV_REPO not in sys.path:
    sys.path.insert(0, _VV_REPO)

_ANALYZABLE = {"totalAssets_type": "external_balanceOf", "defense_strength": 0.5,
               "effective_offset_magnitude": 0.0, "dead_shares": False, "donation_vector": True}


def _bundled_gate() -> str:
    import verivault
    pkg = os.path.dirname(os.path.abspath(verivault.__file__))   # .../verivault/verivault
    return os.path.join(os.path.dirname(pkg), "gate")            # .../verivault/gate


def gate(claim: Claim) -> Verdict:
    try:
        from verivault import audit_signed
        from verivault.autowire import autowire
    except Exception as e:  # noqa
        return Verdict(Status.ABSTAIN, executed=False, reason=f"verivault non importabile: {type(e).__name__}: {e}")

    gate_dir = claim.params.get("gate") or _bundled_gate()
    result_key = claim.params.get("result_key")
    onchain = claim.params.get("onchain")   # se presente: audita un vault DEPLOYATO (mainnet-fork)

    try:
        if onchain:
            from verivault import audit_onchain
            from verivault import certificate as _VC
            test = claim.params.get("test", "test/BenchGate.t.sol")
            vcert = audit_onchain(onchain, gate_dir, test, result_key or "sdai", rpc_url=claim.params.get("rpc"))
            env = _VC.envelope(vcert, key=None)   # Certificate -> busta-dict uniforme
            repro = f"forge fork on-chain {onchain} (gate={gate_dir})"
        else:
            src = claim.target
            if not os.path.exists(src):
                return Verdict(Status.ABSTAIN, executed=False, reason=f"sorgente non trovata: {src}")
            test = claim.params.get("test", "test/GeneralGate.t.sol")
            if result_key:
                env = audit_signed(src, gate_dir, test, result_key)
            else:
                ai = autowire(src, gate_dir)
                try:
                    env = audit_signed(src, gate_dir, ai["gate_test"], ai["result_key"],
                                       llm_fact_fn=lambda s: dict(_ANALYZABLE))
                finally:
                    ai["cleanup"]()
            repro = f"forge test {test} (gate={gate_dir})"
    except Exception as e:  # noqa
        return Verdict(Status.ABSTAIN, executed=False, reason=f"audit fallito: {type(e).__name__}: {e}")

    cert = env["certificate"]
    v = cert["verdict"]
    st = v.get("status")
    reason = v.get("reason", "") or ""
    kind = cert.get("claim", {}).get("kind", "")
    _proof = v.get("proof") or {}
    _cx = v.get("counterexample") or {}

    # FORGE-EXECUTED (recon 2026-06-05): un verdetto vale SOLO se l'exec-gate forge ha DAVVERO girato, ossia porta
    # un profitto-attaccante EVM in wei. Se forge e' assente, il pipeline VeriVault ripiega sullo SCORER euristico
    # (nessuna esecuzione): emetterlo come CONFIRMED-immune con executed=True era un FALSO NEGATIVO su un vault
    # vulnerabile e violava il contratto del kernel ("executed=false -> sospetto"). Niente esecuzione -> ABSTAIN.
    _WEI = ("max_attacker_profit_wei", "attacker_profit_wei", "maxProfit", "max_profit_wei")
    forge_executed = any(k in _proof for k in _WEI) or any(k in _cx for k in _WEI)
    if not forge_executed:
        return Verdict(Status.ABSTAIN, executed=False,
                       reason=f"exec-gate forge NON eseguito (nessun profitto EVM nel verdetto -> fallback scorer "
                              f"euristico, non una prova): {reason}",
                       coverage={"forge_executed": False, "engine": "scorer-fallback", "note": "nessuna esecuzione forge"})

    # VULN = l'immunita' e' REFUTATA: exploit eseguito = controesempio sound -> PROVA
    if st == "REFUTED" or (st == "PASS" and "donation_inflation" in kind):
        return Verdict(Status.REFUTED, executed=True, reason=f"exploit ESEGUITO: {reason}",
                       witness=(_cx or _proof or {}), reproduce=repro,
                       assurance=PROOF, coverage={"method": "forge exec-gate", "counterexample": "executed exploit"})
    # IMMUNE da SWEEP PARAMETRICO: nessun profitto nello spazio spazzato -> confidenza-LIMITATA, NON una prova
    if st == "PASS":
        return Verdict(Status.CONFIRMED, executed=True,
                       reason=f"immunita' (sweep parametrico, confidenza-limitata, non ogni attacco): {reason}",
                       witness=(_proof or {}), reproduce=repro,
                       assurance=BOUNDED, coverage={"method": "forge parametric sweep", "exhaustive": False,
                                                    "note": "spazzato lo spazio donazione/attacco modellato, non ogni attacco possibile"})
    return Verdict(Status.ABSTAIN, executed=False, reason=reason or "ABSTAIN")


def claim_templates(target: str):
    return [Claim(domain="erc4626", target=target, kind="immunity:donation_inflation", params={})]


ERC4626 = Domain(
    name="erc4626",
    gate=gate,
    claim_templates=claim_templates,
    describe="Vault ERC-4626: exec-gate forge (VeriVault) -> REFUTED+exploit | CONFIRMED+prova | ABSTAIN",
)
register(ERC4626)
