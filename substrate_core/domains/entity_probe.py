"""substrate_core.domains.entity_probe — ONTOLOGIA proof-carrying (R1, chiude la breccia).

Il TIPO di un'entita' e' un CERTIFICATO su un PROBE ESEGUITO, mai un'etichetta. Il kernel HARD-CAPPA il tier
per CLASSE di probe (codice no-LLM):

  crypto     (firma / co-spend replay)          -> PROVEN       (prova del controllo/co-proprieta')
  onchain    (ERC-165 / bytecode / interfaccia) -> PROVEN-SPEC  (dichiara l'interfaccia, NON il comportamento)
  behavioral (features determin. + soglie pre-reg) -> EMPIRICAL  (lead falsificabile, NON un fatto; col rischio-residuo)

Il prover puo' PROPORRE un tipo e SCEGLIERE il probe (prover_seam strippa il tipo asserito), ma il GATE ESEGUE
il probe. RISPOSTA al gate comportamentale: la regola e' un classificatore DETERMINISTICO su una FINESTRA-DATI
PINNATA -> ri-eseguibile da chiunque sullo stesso range; e' a UNA VIA (match=lead, non-match=inconcludente);
non sanguina mai il suo livello su un cluster (R2); puo' essere CONTRADDETTA da un probe piu' forte.
"""
from __future__ import annotations

from ..kernel import Claim, Verdict, Status, Domain, register, PROVEN, PROVEN_SPEC, EMPIRICAL
from ..statelight import verify_state_proof   # il kernel come LIGHT CLIENT pluggable (merkle-demo | eth-mpt reale)

# Soglie PRE-REGISTRATE (trasparenti, ri-eseguibili, NON un LLM ne' una black-box).
_BEHAVIOR_RULES = {
    "exchange": lambda f: (f.get("unique_counterparties", 0) > 1000 and 0.7 <= f.get("in_out_ratio", 0) <= 1.3
                           and f.get("deposit_withdraw_symmetry", 0) > 0.6),
    "mixer":    lambda f: (f.get("fan_in", 0) > 50 and f.get("fan_out", 0) > 50
                           and f.get("value_uniformity", 0) > 0.8 and f.get("address_reuse", 1.0) < 0.1),
}
_IFACE = {"erc4626": ("deposit", "redeem", "totalAssets", "convertToShares"),
          "erc20": ("transfer", "balanceOf", "totalSupply")}


def _crypto(p):
    """PROVEN: co-spend replay — a,b co-input nella STESSA tx reale = co-proprieta' (ri-verificabile on-chain)."""
    a, b, co = p.get("a"), p.get("b"), p.get("cospend_inputs")
    if a and b and isinstance(co, (list, tuple)) and a in co and b in co and a != b:
        return Status.CONFIRMED, PROVEN, {"a": a, "b": b, "cospend_tx": p.get("tx"), "rule": "co-input nella stessa tx"}, "", None
    return Status.ABSTAIN, None, {}, "co-spend non dimostrato (a,b non co-input della stessa tx)", None


def _onchain(p):
    """PROVEN-SPEC: interfaccia (ERC-165 / sorgente verificato) -> dichiara il TIPO d'interfaccia, non il comportamento."""
    iface = p.get("interface", "erc4626")
    src = p.get("source", "") or ""
    need = _IFACE.get(iface, ())
    if need and all(fn in src for fn in need):
        return Status.CONFIRMED, PROVEN_SPEC, {"interface": iface, "functions": list(need),
                                               "rule": "tutte le funzioni dell'interfaccia presenti"}, "", None
    return Status.ABSTAIN, None, {}, f"interfaccia '{iface}' non dichiarata", None


def _behavioral(p, candidate):
    """EMPIRICAL: features deterministiche + soglie pre-registrate su una FINESTRA-DATI PINNATA. A UNA VIA."""
    f = p.get("features", {}) or {}
    window = p.get("data_window")
    rule = _BEHAVIOR_RULES.get(candidate)
    if rule is None:
        return Status.ABSTAIN, None, {}, f"nessuna regola comportamentale per '{candidate}'", None
    if not window:
        return Status.ABSTAIN, None, {}, "finestra-dati non PINNATA -> non riproducibile (ermeticita')", None
    resid = float(p.get("calibrated_miss_rate", 0.2))   # onesto: senza calibrazione, EMPIRICAL con rischio dichiarato
    wit = {"candidate": candidate, "features": f, "rule": candidate, "data_window": window}
    if rule(f):
        return Status.CONFIRMED, EMPIRICAL, wit, "le features soddisfano la regola pre-registrata", resid
    # a UNA VIA: non-match NON refuta (la regola potrebbe non coprire un pattern nuovo) -> inconcludente
    return Status.ABSTAIN, None, {**wit, "matched": False}, "le features non soddisfano la regola -> inconcludente", None


def gate(claim: Claim) -> Verdict:
    p = claim.params or {}
    probe = p.get("probe")
    kind = claim.kind or ""
    candidate = kind.split(":", 1)[1] if ":" in kind else p.get("candidate", "")

    # LIGHT CLIENT (chiude il buco dell'oracolo RPC): se il claim e' STATE-BOUND (ha un context con state_root),
    # il dato dev'essere PROVATO incluso in quello state_root via una inclusion-proof VERIFICATA OFFLINE dal kernel.
    ctx = p.get("context")
    if ctx and ctx.get("state_root"):
        sp = p.get("state_proof") or {}
        proof_type = sp.get("proof_type", "merkle-demo")
        if not verify_state_proof(proof_type, {**sp, "state_root": ctx.get("state_root")}):
            return Verdict(Status.ABSTAIN, executed=True,
                           reason=f"invalid-data-proof ({proof_type}): il dato non e' provato incluso nello state_root "
                                  "dichiarato (il kernel VERIFICA la prova, non si fida del nodo RPC)",
                           coverage={"state_root": ctx.get("state_root"), "proof_type": proof_type, "light_client": True})

    # PROVEN richiede una PROVA, non una lista ASSERITA (recon 2026-06-05): il probe 'crypto' (co-proprieta',
    # tier PROVEN) deve esibire una inclusion-proof VALIDA (verificata sopra dal light-client) legata a un
    # context.state_root PINNATO, e quel leaf deve committare gli input (a,b) dichiarati. Senza -> ABSTAIN.
    # Chiude il conio di un falso PROVEN da cospend_inputs fabbricati (sopravviveva anche al prover_seam).
    if probe == "crypto":
        sp = p.get("state_proof") or {}
        if not (ctx and ctx.get("state_root") and sp):
            return Verdict(Status.ABSTAIN, executed=True,
                           reason="needs-proof: la co-proprieta' (tier PROVEN) richiede una inclusion-proof legata a "
                                  "uno state_root PINNATO; i cospend_inputs ASSERITI non bastano (anti-conio)",
                           coverage={"probe_class": "crypto", "entity_type_candidate": candidate, "needs_proof": True})
        # ANTI LEAF-DECOUPLING (recon 2026-06-05): la prova che lega (a,b) dev'essere QUELLA verificata dal
        # light-client. eth-mpt prova lo STATO di un ACCOUNT (non una co-spesa) e il suo `leaf` NON e' verificato
        # -> un attaccante accoppiava una eth-mpt reale a un `leaf` fabbricato {inputs:[a,b]} per coniare un PROVEN
        # su a,b non correlati. Accettiamo solo prove il cui LEAF e' DAVVERO verificato a legare a,b (merkle-demo).
        proof_type = sp.get("proof_type", "merkle-demo")
        if proof_type != "merkle-demo":
            return Verdict(Status.ABSTAIN, executed=True,
                           reason=f"needs-proof: proof_type '{proof_type}' NON prova la co-spesa (eth-mpt prova lo stato "
                                  "di un account, non la co-proprieta'); serve una prova il cui leaf VERIFICATO leghi (a,b)",
                           coverage={"probe_class": "crypto", "entity_type_candidate": candidate, "needs_proof": True,
                                     "rejected_proof_type": proof_type})
        leaf = sp.get("leaf") or {}
        leaf_inputs = leaf.get("inputs")
        a, b = p.get("a"), p.get("b")
        if not (isinstance(leaf_inputs, (list, tuple)) and a in leaf_inputs and b in leaf_inputs and a != b):
            return Verdict(Status.ABSTAIN, executed=True,
                           reason="needs-proof: il leaf VERIFICATO non committa (a,b) come ELEMENTI distinti della lista "
                                  "inputs -> la prova non riguarda questa co-spesa (anti leaf-decoupling / substring)",
                           coverage={"probe_class": "crypto", "entity_type_candidate": candidate, "needs_proof": True})

    table = {"crypto": _crypto, "onchain": _onchain}
    if probe in table:
        st, asr, wit, reason, resid = table[probe](p)
    elif probe == "behavioral":
        st, asr, wit, reason, resid = _behavioral(p, candidate)
    else:
        return Verdict(Status.ABSTAIN, executed=False, reason=f"probe sconosciuto: {probe!r} (crypto|onchain|behavioral)")
    if st == Status.ABSTAIN:
        return Verdict(Status.ABSTAIN, executed=True, reason=reason or "probe non concludente",
                       coverage={"probe_class": probe, "entity_type_candidate": candidate})
    caveat = ("PROVEN sound SOLO se lo state_root proviene da una fonte fidata/verificata (es. eth-mpt su un "
              "blocco reale); con merkle-demo la radice e' auto-asserita dal prover (didattico)" if probe == "crypto" else "")
    return Verdict(st, executed=True,
                   reason=f"probe '{probe}' eseguito -> tipo '{candidate}' {st.value} (tier {asr})"
                          + (f"; {reason}" if reason else ""),
                   witness=wit, reproduce=f"entity_probe[{probe}] su {claim.target}",
                   assurance=asr, coverage={"probe_class": probe, "entity_type": candidate},
                   residual_risk=resid, assurance_caveat=caveat)


def claim_templates(target: str):
    return [Claim(domain="entity_probe", target=target, kind="entity_type:unknown", params={"probe": "onchain"})]


ENTITY_PROBE = Domain(name="entity_probe", gate=gate, claim_templates=claim_templates,
                      describe="Ontologia proof-carrying: tipo d'entita' = cert su PROBE ESEGUITO "
                               "(crypto->PROVEN, onchain->PROVEN-SPEC, behavioral->EMPIRICAL)")
register(ENTITY_PROBE)
