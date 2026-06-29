"""substrate_core.investigator — INVESTIGAZIONE PROOF-CARRYING.

Estende il kernel da "verifica un claim" a "INDAGA una domanda". Un organismo naviga un grafo di evidenza
(flussi di fondi / transazioni), e a OGNI passo forma un claim adjudicato PER ESECUZIONE contro i dati,
segue le piste non-refutate, e RENDICONTA ogni unita' di valore: tracciata (CONFIRMED), oscurata da un
mixer (ABSTAIN onesto), o polvere sotto soglia. La conclusione e' una CATENA di certificati eseguiti +
un bilancio che riconcilia il totale. Mai un'asserzione senza esecuzione.

Sorgente-evidenza astratta (EvidenceGraph): la stessa engine gira su dati SINTETICI (demo provabile) o su
un ledger pubblico REALE (adapter on-chain). L'engine e' identico; cambia solo la sorgente.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

from .kernel import Claim, Verdict, Status, Certificate, envelope, compose_bundle, PROOF, BOUNDED, NONE


@dataclass
class Flow:
    frm: str
    to: str
    amount: float
    ref: str          # id transazione / riferimento ri-verificabile


class EvidenceGraph:
    """Sorgente di evidenza navigabile. Implementazione in-memory (sintetica) o adattata a dati reali."""
    def __init__(self):
        self._edges: Dict[str, List[Flow]] = defaultdict(list)
        self.labels: Dict[str, str] = {}

    def add_flow(self, frm: str, to: str, amount: float, ref: str) -> None:
        self._edges[frm].append(Flow(frm, to, amount, ref))

    def label(self, node: str, tag: str) -> None:
        self.labels[node] = tag

    def outflows(self, node: str) -> List[Flow]:
        return self._edges.get(node, [])

    def has_flow(self, frm: str, to: str, ref: str) -> bool:
        """Ri-esegue la verifica del singolo hop contro i dati (il 'gate' di un passo d'indagine)."""
        return any(f.to == to and f.ref == ref for f in self._edges.get(frm, []))


# --------------------------------------------------------------------------------------
# L'engine: tracciamento taint con hop ESEGUITI + bilancio onesto
# --------------------------------------------------------------------------------------

def trace_funds(graph: EvidenceGraph, seed: str, seed_amount: float, *,
                threshold: float = 1.0, key: Optional[bytes] = None, stamp: str = "",
                max_steps: int = 2000) -> dict:
    """Traccia `seed_amount` uscito da `seed` lungo i flussi dominanti. Ogni propagazione >= threshold
    e' un HOP ESEGUITO (verificato contro i dati). Riconcilia: tracciato-a-sink / oscurato-da-mixer / polvere."""
    frontier: Dict[str, float] = {seed: float(seed_amount)}
    hop_certs: List[dict] = []
    sinks: Dict[str, float] = defaultdict(float)        # nodo terminale/exchange -> tainted ricevuto
    obscured: Dict[str, float] = defaultdict(float)     # mixer -> tainted entrato (non tracciabile oltre)
    dust = 0.0
    steps = 0

    while frontier and steps < max_steps:
        node, amt = max(frontier.items(), key=lambda kv: kv[1])
        del frontier[node]
        if amt < threshold:
            dust += amt
            continue
        tag = graph.labels.get(node, "")
        outs = graph.outflows(node)
        total_out = sum(f.amount for f in outs)

        if tag == "mixer":
            obscured[node] += amt                       # ABSTAIN onesto: non si traccia oltre un mixer
            continue
        if tag in ("cashout-exchange", "terminal") or not outs or total_out == 0:
            sinks[node] += amt                          # i fondi si fermano qui (cash-out / foglia)
            continue

        for f in outs:                                  # il taint segue il denaro, proporzionale al peso
            share = amt * (f.amount / total_out)
            if share < threshold:
                dust += share
                continue
            ok = graph.has_flow(f.frm, f.to, f.ref)     # ESECUZIONE: il flusso esiste nei dati?
            v = Verdict(
                Status.CONFIRMED if ok else Status.ABSTAIN,
                executed=True,
                reason=(f"flusso tainted ~{share:.0f} {f.frm}->{f.to} confermato nei dati"
                        if ok else f"flusso {f.frm}->{f.to} non confermato"),
                witness={"from": f.frm, "to": f.to, "tainted": round(share, 2),
                         "edge_amount": f.amount, "ref": f.ref},
                reproduce=f"EvidenceGraph.has_flow({f.frm!r}, {f.to!r}, ref={f.ref!r})",
                # una transazione che ESISTE nei dati e' una PROVA che e' avvenuta
                assurance=PROOF if ok else NONE,
                coverage={"method": "ledger lookup (has_flow)"},
            )
            cert = envelope(Certificate(Claim("flowtrace", f"{f.frm}->{f.to}", "tainted_flow",
                                              {"ref": f.ref, "tainted": round(share, 2)}),
                                        v, engine="investigator", stamp=stamp), key=key, stamp=stamp)
            hop_certs.append(cert)
            if ok:
                frontier[f.to] = frontier.get(f.to, 0.0) + share
            steps += 1

    traced = sum(sinks.values())
    obsc = sum(obscured.values())
    return {
        "seed": seed, "seed_amount": float(seed_amount),
        "hops": hop_certs,
        "sinks": dict(sinks), "obscured": dict(obscured), "dust": round(dust, 2),
        "reconciliation": {"traced_to_sinks": round(traced, 2), "obscured_by_mixers": round(obsc, 2),
                           "dust_below_threshold": round(dust, 2),
                           "accounted": round(traced + obsc + dust, 2)},
    }


def investigation_certificate(result: dict, *, key: Optional[bytes] = None, stamp: str = "") -> dict:
    """Compone gli hop eseguiti in UN certificato d'indagine + la conclusione riconciliata."""
    rec = result["reconciliation"]
    seed_amt = result["seed_amount"]
    fully_accounted = abs(rec["accounted"] - seed_amt) < max(1.0, 1e-6 * seed_amt)
    # l'indagine "regge" se ogni hop tracciato e' CONFIRMED e il bilancio chiude
    all_hops_ok = all(h["certificate"]["verdict"]["status"] == "CONFIRMED" for h in result["hops"]) if result["hops"] else False
    status = Status.CONFIRMED if (all_hops_ok and fully_accounted) else Status.ABSTAIN
    # assurance: ogni hop e' una prova, MA se un mixer oscura parte del totale la CONCLUSIONE
    # ("dove sono finiti TUTTI i soldi") non e' una prova -> scende a bounded.
    obscured_total = sum(result["obscured"].values())
    if status == Status.CONFIRMED:
        assurance = PROOF if obscured_total == 0 else BOUNDED
    else:
        assurance = NONE
    reason = (f"tracciati {rec['traced_to_sinks']:.0f} a sink, {rec['obscured_by_mixers']:.0f} oscurati da mixer, "
              f"{rec['dust_below_threshold']:.0f} polvere; bilancio {'CHIUSO' if fully_accounted else 'APERTO'} "
              f"su {seed_amt:.0f}; {len(result['hops'])} hop eseguiti; assurance={assurance}")
    claim = Claim("investigation", result["seed"], "fund_trace",
                  {"seed_amount": seed_amt, "sinks": result["sinks"], "obscured": result["obscured"],
                   "hop_hashes": [h["content_hash"] for h in result["hops"]]})
    cert = Certificate(claim, Verdict(status, executed=True, reason=reason, witness=rec,
                                      reproduce="substrate_core.investigator.trace_funds(...)",
                                      assurance=assurance, coverage={"hops": len(result["hops"]),
                                                                     "obscured_total": round(obscured_total, 2)}),
                       engine="investigator", stamp=stamp)
    return envelope(cert, key=key, stamp=stamp)
