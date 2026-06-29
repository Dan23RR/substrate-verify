"""
verivault.oracles.base — l'interfaccia ORACOLO (il primitivo agnostico).

Ogni dominio = una scelta di oracoli; il substrato di adjudicazione e' UNO.
Tutti gli oracoli condividono una firma:  Claim -> Verdict {PASS | REFUTED+controesempio | ABSTAIN+motivo}.

Famiglie di oracoli (tutte tecnologia matura):
  - esecuzione-su-fork (forge): il PoC gira su stato reale (positivo) / sweep->certificato-immunita (negativo)
  - regola-deterministica / SMT su fatti estratti (lo scorer W5, Z3 per arrotondamenti)
  - replica-multi-seed (anti-Schaeffer: se il claim svanisce cambiando seed/metrica continua -> REFUTED)
DISCIPLINA: un oracolo deve DISPORRE binariamente. Un secondo modello probabilistico (NLI/entailment)
NON e' un oracolo sound -> non usarlo per chiudere il gate (e' il punto debole strutturale, vedi docs/MOAT.md).
"""
from __future__ import annotations
import abc
from ..schemas import Claim, Verdict, Status


class Oracle(abc.ABC):
    """ABC: implementa `decide(claim) -> Verdict`. Deve essere DETERMINISTICO e citare la sua provenance."""
    name: str = "oracle"

    @abc.abstractmethod
    def decide(self, claim: Claim) -> Verdict:
        ...

    def supports(self, claim: Claim) -> bool:
        return claim.oracle == self.name


class OracleRegistry:
    """Instrada ogni claim all'oracolo del suo tipo. Se nessuno lo supporta -> ABSTAIN tipizzato."""
    def __init__(self) -> None:
        self._oracles: dict[str, Oracle] = {}

    def register(self, oracle: Oracle) -> None:
        self._oracles[oracle.name] = oracle

    def decide(self, claim: Claim) -> Verdict:
        o = self._oracles.get(claim.oracle)
        if o is None:
            return Verdict(Status.ABSTAIN, reason=f"nessun oracolo registrato per '{claim.oracle}'")
        return o.decide(claim)
