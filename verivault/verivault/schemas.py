"""
verivault.schemas — il kernel VERIFICATION-NATIVE (agnostico).

Principio (misurato in questa ricerca, non slogan): VALORE = creativita-LLM (PROPONE)
+ grounding-deterministico (ORACOLO dispone binariamente) + cancello-di-falsificazione
(REFUTED non esce) + COMPOSIZIONE (claim certificati che si compongono).

L'unita atomica di output NON e' testo: e' un CLAIM che porta il proprio certificato.
Tre stati first-class:  PASS | REFUTED(+controesempio) | ABSTAIN(+motivo tipizzato).
Questo modulo e' DOMINIO-AGNOSTICO: cambia solo la libreria di oracoli.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Status(str, Enum):
    PASS = "PASS"            # un oracolo deterministico ha confermato il claim
    REFUTED = "REFUTED"      # un controesempio lo ha ucciso -> NON esce all'utente
    ABSTAIN = "ABSTAIN"      # nessun oracolo puo decidere -> dichiarato, mai un finto-verdetto


@dataclass
class Claim:
    """Asserzione tipizzata atomica che il modello PROPONE. Il 'fatto' che l'LLM da solo
    sbaglia (data-flow, reachability) diventa un campo esplicito, non prosa da fidarsi."""
    kind: str                      # es. 'erc4626.donation_inflation', 'erc4626.immunity'
    payload: dict[str, Any]        # fatti tipizzati (totalAssets_type, offset, dead_shares, ...)
    oracle: str                    # quale oracolo deve disporre ('forge_gate', 'smt', ...)
    target: str                    # cosa (path .sol / indirizzo on-chain+block)
    deps: list[str] = field(default_factory=list)  # claim da cui dipende (composizione)


@dataclass
class Verdict:
    """Esito dell'oracolo su un Claim. counterexample/proof citano sempre l'artefatto reale."""
    status: Status
    confidence: float = 0.0        # continuo (anti-Schaeffer); usato dalla calibrazione conforme
    counterexample: Optional[dict] = None   # per REFUTED / per il gate POSITIVO (es. PoC che gira)
    proof: Optional[dict] = None            # per PASS / per il gate NEGATIVO (es. certificato-immunita)
    reason: str = ""               # motivo tipizzato (obbligatorio per ABSTAIN)
    script: str = ""               # lo script/esecuzione che ha prodotto il numero (provenance)
    cost: dict[str, Any] = field(default_factory=dict)  # $/forge-min/token


@dataclass
class Certificate:
    """L'artefatto firmato e PORTABILE che esce: {claim, verdetto, controesempio-o-prova, costo}.
    Contestabile: chiunque puo ri-girare l'oracolo e UCCIDERE un claim falso (refutazione = feature)."""
    claim: Claim
    verdict: Verdict
    composed_from: list[str] = field(default_factory=list)
    # un claim composto eredita il certificato PIU DEBOLE della sua catena (anello peggiore)

    @property
    def emits(self) -> bool:
        """Regola del refute-gate: esce solo PASS o ABSTAIN-dichiarato; REFUTED viene soppresso."""
        return self.verdict.status in (Status.PASS, Status.ABSTAIN)
