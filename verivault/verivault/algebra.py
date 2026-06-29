"""
verivault.algebra — BOUND ECONOMICI COMPONIBILI (il salto disruptive: Proof-Carrying Audit a livello protocollo).

Trasforma ogni certificato d'immunita in un BOUND ECONOMICO quantitativo e lo compone con l'operatore
weakest-link JOIN. Tesi sound-by-construction (SOLO sotto isolamento-flusso-fondi):

    MEV(A ∘ B) ≤ max(MEV(A), MEV(B))        [vale se i link sono MONOTONI / isolati]

KILL-CONDITION (anti-ASTRA, pre-dichiarata): se due link sono singolarmente immuni (max_profit ≤ 0) ma la
COMPOSIZIONE e sfruttabile (coupling super-additivo: oracolo condiviso, reentrancy cross-vault, flash-loan che
accoppia i flussi), allora la disuguaglianza weakest-link e FALSA. In quel caso JOIN NON deve emettere un
certificato-SAFE composto: si DECLASSA a 'triage' (sound=False -> ABSTAIN sul whole-protocol). Onesto, non gonfiato.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class EconomicBound:
    """Bound superiore sul profitto-attaccante per una proprieta/contratto, su un range di validita."""
    max_profit_wei: int        # upper bound su MEV per questo link (<=0 = immune)
    range_k: float             # validita: donazione/parametro in [0, k*v]
    monotone: bool             # True se fund-flow ISOLATO (nessun coupling super-additivo verso altri link)
    source: str

    @property
    def immune(self) -> bool:
        return self.max_profit_wei <= 0


def join(bounds: list[EconomicBound]) -> tuple[EconomicBound, bool]:
    """Weakest-link: il bound composto = il PEGGIOR link (max dei max_profit), range = intersezione.
    Ritorna (bound_composto, sound). sound=True solo se TUTTI i link sono monotoni (isolamento-flusso-fondi):
    in caso contrario il bound e una EURISTICA DI TRIAGE, non una prova (vedi kill-condition nel docstring)."""
    if not bounds:
        return EconomicBound(0, 0.0, True, "join()"), True
    worst = max(b.max_profit_wei for b in bounds)
    rng = min(b.range_k for b in bounds)
    sound = all(b.monotone for b in bounds)
    src = "join(" + ",".join(b.source for b in bounds) + ")"
    return EconomicBound(worst, rng, sound, src), sound


def protocol_verdict(bounds: list[EconomicBound]) -> tuple[str, EconomicBound, bool]:
    """Verdetto whole-protocol dal JOIN. Disciplina:
      - un link non-immune        -> 'VULN'   (il composto eredita il link bucato; sound)
      - tutti immuni MA non-sound -> 'ABSTAIN' (coupling super-additivo: triage, non prova) <- la kill onesta
      - tutti immuni E sound      -> 'IMMUNE'  (certificato-protocollo sound by construction)
    """
    b, sound = join(bounds)
    if not b.immune:
        return "VULN", b, sound
    if not sound:
        return "ABSTAIN", b, sound          # weakest-link non garantito sotto coupling -> NON certificare safe
    return "IMMUNE", b, sound


def monotone_from_dependency(external_flash_oracle: bool) -> bool:
    """Deriva `monotone` dalla STRUTTURA (non a mano): un link e' isolato (monotone) SOLO se la sua sicurezza NON
    dipende da un oracolo-prezzo ESTERNO flash-manipolabile.

    GIUSTIFICAZIONE EMPIRICA (eseguita, non assunta):
      - `gate/test/OracleCoupledGate.t.sol` (PASS): due componenti singolarmente safe (AMM swap-venue con fee reale;
        prestito fair) compongono in profit MISURATO +78e21 > max(singoli) quando il prestito legge lo spot-AMM
        manipolabile -> super-additivo -> il link NON e' monotono (monotone=False).
      - `gate/test/CoupledGate.t.sol` (PASS): la composizione vault-interna (vault immune + prestito con custodia,
        SENZA oracolo-esterno) REGGE (tutte <= max singoli) -> il link resta monotono (monotone=True).
    Cosi' il flag non e' piu' hand-set: e' una proprieta' strutturale falsificabile (la dipendenza-oracolo)."""
    return not external_flash_oracle
