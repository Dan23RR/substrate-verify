"""
verivault.pipeline — il loop VERIFICATION-NATIVE a 5 stadi (decompose -> ground -> refute-gate -> compose).
Identico in ogni dominio; cambia solo la libreria di oracoli (agnostico).

  [1] extract  : fatti tipizzati (LLM-fact-extractor o deterministico)        -> stage1_extract
  [2] score    : rischio continuo deterministico (anti-Schaeffer)              -> stage2_score
  [3] propose  : l'orchestratore (LLM) costruisce il Claim + l'harness         -> TODO(aether MIT)
  [4] ground   : l'ORACOLO eseguibile dispone (forge gate bidirezionale)       -> oracles.forge_gate
  [5] calibrate: output a 3 vie {VULN+PoC | SAFE+cert | ABSTAIN+banda}         -> stage5_calibrate

Output: un Certificate firmato e portabile. REFUTED non esce (refute-gate).
"""
from __future__ import annotations
from typing import Any, Optional, Callable
from .schemas import Claim, Certificate, Verdict, Status
from .stage1_extract import extract_facts
from .stage2_score import defense_risk
from .stage5_calibrate import calibrate
from .oracles.base import OracleRegistry
from .oracles.forge_gate import ForgeGateOracle
from .oracles.smt_rounding import SmtRoundingOracle


def build_default_registry() -> OracleRegistry:
    r = OracleRegistry()
    r.register(ForgeGateOracle())
    r.register(SmtRoundingOracle())     # T1 (sound; valore = certificato-continuo + witness, vedi cascade.py)
    return r


def audit(sol_path: str,
          registry: Optional[OracleRegistry] = None,
          llm_fact_fn: Optional[Callable[[str], dict]] = None,
          conformal_threshold_value: float = 0.5,
          run_exec_gate: bool = False,
          gate_test_path: Optional[str] = None,
          gate_result_key: Optional[str] = None) -> Certificate:
    """Pipeline end-to-end su un contratto. `run_exec_gate=True` invoca il gate forge (Stadio 4).
    `llm_fact_fn` inietta l'estrattore semantico (Stadio 1, W5-v2). Senza, usa il deterministico."""
    registry = registry or build_default_registry()

    facts = extract_facts(sol_path, llm_fact_fn=llm_fact_fn)                 # [1]
    risk, analyzable = defense_risk(facts)                                  # [2]

    claim = Claim(kind="erc4626.donation_inflation", payload=dict(facts), oracle="forge_gate",
                  target=sol_path)                                          # [3] (orchestratore: TODO aether)

    gate = None
    if run_exec_gate and analyzable:                                        # [4] cascata tiered T0->T1->T3
        if gate_test_path:
            claim.payload["test_path"] = gate_test_path
        if gate_result_key:                      # FP=0: senza result_key il gate ABSTIENE (no blind-max)
            claim.payload["result_key"] = gate_result_key
        # BRICK 3: instrada via run_cascade -> l'EXEC-GATE forge e' l'adjudicatore (conseguenza di BRICK 4:
        # lo scorer NON e' un gate autonomo affidabile). T0 puo' astenersi cheap su risk<0.05 (conservativo:
        # ABSTAIN, mai falso-SAFE); T1 SMT fa da shortcut se modellabile (ABSTAIN se z3 assente); T3 forge decide.
        from .cascade import run_cascade
        gate = run_cascade(claim, registry, risk=risk)

    return calibrate(claim, risk, analyzable, gate, conformal_threshold_value)  # [5]


def audit_realcode(sol_path: str, gate_dir: str, gate_test: str, result_key: str,
                   llm_fact_fn: Optional[Callable[[str], dict]] = None,
                   conformal_threshold_value: float = 0.5) -> Certificate:
    """LOOP END-TO-END SU CODICE REALE: extract(LLM) -> score -> exec-gate REALE (forge sul contratto vero)
    -> certificato firmato. L'exec-gate e' BIDIREZIONALE: emette il certificato della POLARITA giusta
    (VULN+witness eseguito, o IMMUNE+certificato), ENTRAMBI Status.PASS (entrambi escono dal refute-gate).

      gate_dir   = progetto forge che contiene il contratto reale + l'harness d'attacco
      gate_test  = path del test-harness (es. 'test/RealSolmateGate.t.sol')
      result_key = quale riga RESULT del gate adjudica questo target (es. 'solmate_balanceof')
    """
    facts = extract_facts(sol_path, llm_fact_fn=llm_fact_fn)                  # [1] estrai fatti tipizzati
    risk, analyzable = defense_risk(facts)                                    # [2] score continuo

    claim = Claim(kind="erc4626.immunity", oracle="forge_gate", target=sol_path,   # [3] proponi (polarita-immunita)
                  payload={**facts, "test_path": gate_test, "result_key": result_key})

    if not analyzable:                                                        # astensione onesta (no exec-gate)
        return calibrate(claim, risk, analyzable, None, conformal_threshold_value)

    gate = ForgeGateOracle(forge_dir=gate_dir).decide(claim)                  # [4] ESEGUI l'exec-gate sul codice reale

    # [5] normalizza bidirezionalmente: il segno di maxProfit decide la polarita; entrambe le polarita ESCONO (PASS)
    if gate.status == Status.REFUTED:
        # immunita REFUTATA = VULN ESEGUITA -> ri-incarta come claim-VULN confermato (PASS) col witness D*
        vuln = Claim(kind="erc4626.donation_inflation", oracle="forge_gate", target=sol_path, payload=dict(facts))
        vv = Verdict(Status.PASS, confidence=1.0, counterexample=gate.counterexample,
                     proof={"vulnerable": True, "scorer_risk": round(risk, 3)},
                     reason="exec-gate: exploit ESEGUITO su codice reale -> VULN confermata", script=gate.script)
        return Certificate(vuln, vv)
    if gate.status == Status.PASS:                                            # immune: certificato ESEGUITO
        gate.proof = {**(gate.proof or {}), "scorer_risk": round(risk, 3)}
        return Certificate(claim, gate)
    return calibrate(claim, risk, analyzable, gate, conformal_threshold_value)  # ABSTAIN -> fallback scorer


def audit_onchain(address: str, gate_dir: str, gate_test: str, result_key: str,
                  rpc_url: Optional[str] = None, block: Optional[int] = None,
                  conformal_threshold_value: float = 0.5) -> Certificate:
    """PRODUCT API (mattone enterprise, gap e): audit di un contratto DEPLOYATO on-chain. Riusa lo STESSO exec-gate
    bidirezionale + kernel del flusso source (audit_realcode). Il fork on-chain (vm.createSelectFork) RICHIEDE un RPC:
      - senza RPC -> ABSTAIN DICHIARATO (mai un finto-verdetto; il flusso source/offline resta disponibile);
      - con RPC   -> esegue il fork-gate e ritorna il Certificate (VULN+witness eseguito | IMMUNE+certificato).
    Scope onesto: copre le classi-vuln con un harness fork-parametrico scritto (oggi inflation), non un contratto arbitrario."""
    import os
    rpc = rpc_url or os.environ.get("ETH_RPC_URL")
    target = f"onchain:{address}@{block if block is not None else 'latest'}"
    claim = Claim(kind="erc4626.immunity", oracle="forge_gate", target=target,
                  payload={"test_path": gate_test, "result_key": result_key,
                           "address": address, "block": block, "closed_form_model": False})
    if not rpc:
        return Certificate(claim, Verdict(Status.ABSTAIN, script=gate_test,
            reason="audit_onchain richiede ETH_RPC_URL per il fork on-chain; nessun RPC -> astensione dichiarata "
                   "(mai finto-verdetto). Il flusso source (audit_realcode) e l'exec-gate offline restano disponibili."))
    os.environ.setdefault("ETH_RPC_URL", rpc)
    gate = ForgeGateOracle(forge_dir=gate_dir).decide(claim)                  # fork-gate (richiede RPC nel subprocess)
    if gate.status == Status.REFUTED:                                        # immunita refutata on-chain = VULN eseguita
        vuln = Claim(kind="erc4626.donation_inflation", oracle="forge_gate", target=target, payload=dict(claim.payload))
        return Certificate(vuln, Verdict(Status.PASS, confidence=1.0, counterexample=gate.counterexample,
            proof={"vulnerable": True, "onchain": address}, reason="fork-gate on-chain: exploit ESEGUITO -> VULN", script=gate.script))
    return Certificate(claim, gate)


def audit_signed(sol_path: str, gate_dir: str, gate_test: str, result_key: str,
                 signing_key: Optional[bytes] = None, **kw) -> dict:
    """PRODUCT: flusso end-to-end  source -> exec-gate -> CERTIFICATO FIRMATO PORTABILE (busta con content_hash + HMAC).
    Lega audit_realcode (moat exec-gate L4) + certificate.envelope (firma/portabilita/contestabilita). Output enterprise consegnabile."""
    from .certificate import envelope
    cert = audit_realcode(sol_path, gate_dir, gate_test, result_key, **kw)
    return envelope(cert, key=signing_key)


def audit_immunity_demo() -> Certificate:
    """Demo del fossato (gate negativo) sui modelli validati: ritorna il Certificate del certificato-immunita."""
    reg = build_default_registry()
    claim = Claim(kind="erc4626.immunity", payload={"test_path": "test/ImmunityCert.t.sol",
                  "result_key": "oz:offset0"}, oracle="forge_gate", target="forge/test/ImmunityCert.t.sol")
    v = reg.decide(claim)
    return Certificate(claim, v)
