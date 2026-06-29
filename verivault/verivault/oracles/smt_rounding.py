"""
verivault.oracles.smt_rounding — TIER T1: oracolo SMT (Z3) per la disuguaglianza di arrotondamento ERC-4626.

Il fossato approfondito: invece di campionare 9 punti (grid di ImmunityCert.t.sol), Z3 decide sul CONTINUO
[0, k*v] la donazione D che rende l'attacco first-depositor profittevole:
  - SAT  -> ritorna il WITNESS esatto D*  (che l'exec-gate T3 esegue -> PoC garantito-violante, FP resta 0)
  - UNSAT -> CERTIFICATO DI IMMUNITA sul CONTINUO (non solo sui 9 punti)

SCOPE ONESTO (corretto dal workflow): vale per la classe OZ/raw a forma-chiusa nota (modello first-depositor
S=A=0, vittima singola). Su contratto reale la conversione non e' nota a priori -> generalizzazione = serve
estrattore-formula-LLM (gated da T3) o halmos (subprocess AGPL). T1 e' GENERATORE-DI-WITNESS, mai oracolo
finale: un D* sbagliato -> il forge-gate fallisce -> ABSTAIN, FP=0. Il rischio e' su RECALL, non su FP.

Aritmetica IDENTICA al forge (floor integer): vedi forge/test/ImmunityCert.t.sol.
"""
from __future__ import annotations
from ..schemas import Claim, Verdict, Status
from .base import Oracle

# z3 e' il tier-T1 OPZIONALE. Il CORE (kernel + exec-gate forge, il moat form-agnostico) NON lo richiede.
# Import LAZY/GUARDATO: se z3 manca, l'oracolo SMT ABSTIENE (mai crash dell'import, mai finto-verdetto).
# Questo e' coerente con la disciplina verification-native: un tier indisponibile si dichiara, non si finge.
try:
    import z3
    _Z3_AVAILABLE = True
except ImportError:  # noqa: z3-solver non installato -> il package resta importabile, l'SMT degrada ad ABSTAIN
    z3 = None
    _Z3_AVAILABLE = False


def _profit_expr(D, O: int, V: int, raw: bool):
    """profitto attaccante (z3 Int) come funzione della donazione D. Aritmetica floor identica al forge."""
    if raw:
        # RawVault: deposit 1 (S=1,A=1) ; donate D (A=1+D) ; victim V: sv=V*1/(1+D) ; redeem 1: got=(1+D+V)/(1+sv)
        sv = (V * 1) / (1 + D)
        got = (1 + D + V) / (1 + sv)
        return got - 1 - D
    else:
        # OZVault(O): deposit 1 -> sa=O (S=O,A=1) ; donate D (A=1+D) ; victim V: sv=V*2O/(D+2) ;
        #             redeem O: got=O*(D+V+2)/(2O+sv)
        sv = (V * 2 * O) / (D + 2)
        got = (O * (D + V + 2)) / (2 * O + sv)
        return got - 1 - D


def synthesize(O: int, V: int, k: int, raw: bool = False) -> tuple[str, int | None]:
    """SAT -> ('SAT', D*) ; UNSAT-in-bound -> ('UNSAT', None). z3 div = floor per operandi nonneg."""
    if not _Z3_AVAILABLE:
        raise RuntimeError("tier-T1 SMT richiede z3: `pip install z3-solver`. "
                           "Il CORE (kernel + exec-gate forge, il moat) NON lo richiede.")
    D = z3.Int("D")
    profit = _profit_expr(D, O, V, raw)
    s = z3.Solver()
    s.add(D >= 0, D <= k * V, profit > 0)
    if s.check() == z3.sat:
        return "SAT", s.model()[D].as_long()
    return "UNSAT", None


class SmtRoundingOracle(Oracle):
    name = "smt"

    # feature che ROMPONO la forma-chiusa OZ/raw -> il solver NON puo modellarle (deve ABSTAIN, non indovinare)
    _UNMODELABLE = ("fee_bps", "dynamic_fee", "multi_step_conversion", "hook_on_deposit",
                    "non_standard_accounting", "rebasing_asset")

    def supports(self, claim: Claim) -> bool:
        """SCOPE ESPLICITO (anti-fragilita dichiarata nel codice): l'SMT modella SOLO il first-depositor
        donation su accounting OZ/raw a forma-chiusa. Fee dinamiche pre-deposito, conversioni multi-passo,
        hook/reentrancy, asset rebasing -> FUORI SCOPE -> ABSTAIN (e l'exec-gate forge, form-AGNOSTICO, decide)."""
        p = claim.payload
        if any(p.get(k) for k in self._UNMODELABLE):
            return False
        if float(p.get("fee_bps", 0) or 0) > 0:
            return False
        if int(p.get("conversion_steps", 1) or 1) > 1:
            return False
        tat = p.get("totalAssets_type")
        if tat is not None and tat not in ("internal_accounting", "external_balanceOf"):
            return False
        return True

    def decide(self, claim: Claim) -> Verdict:
        if not _Z3_AVAILABLE:                       # z3 assente -> ABSTAIN dichiarato, mai crash, mai finto-verdetto
            return Verdict(Status.ABSTAIN, confidence=0.0,
                           reason="tier-T1 SMT non disponibile (z3 non installato) -> defer all'exec-gate "
                                  "forge (form-agnostico: chiama l'ABI reale). Il CORE non richiede z3.",
                           script="smt_rounding.py")
        p = claim.payload
        if not self.supports(claim):
            return Verdict(Status.ABSTAIN, confidence=0.0,
                           reason="SMT fuori-scope (fee dinamica / multi-step / hook / accounting non-standard) "
                                  "-> defer all'exec-gate forge (form-agnostico: chiama l'ABI reale)",
                           script="smt_rounding.py")
        try:
            O = int(p.get("effective_offset_magnitude", 0) or 0)
            V = int(p.get("victim_deposit", 10 ** 18))
            k = int(p.get("max_donation_multiple", 100))
            raw = (O <= 0) or bool(p.get("raw_pattern"))
            O_eff = O if O > 0 else 1
        except Exception as e:  # noqa
            return Verdict(Status.ABSTAIN, reason=f"payload non modellabile in SMT: {e}", script="smt_rounding.py")
        status, witness = synthesize(O_eff, V, k, raw=raw)
        if status == "SAT":
            return Verdict(Status.PASS if not claim.kind.endswith("immunity") else Status.REFUTED,
                           confidence=1.0,
                           counterexample={"donation_witness_wei": witness,
                                           "note": "esegui questo D* nel forge-gate (T3) per la prova"},
                           reason=f"z3: esiste D*={witness} che rende l'attacco profittevole",
                           script="smt_rounding.py")
        # UNSAT in bound: immune SUL MODELLO a forma-chiusa assunto (OZ/raw), NON sul bytecode deployato.
        # Per kind!=immunity (claim su CODICE REALE) NON emettere 'immunity_certificate' (sopprimerebbe una VULN
        # su fatti mislabelati): usa 'model_immunity_hint' -> la cascata NON short-circuita, T3 forge decide (review).
        is_immunity = claim.kind.endswith("immunity")
        key = "immunity_certificate" if is_immunity else "model_immunity_hint"
        return Verdict(Status.PASS if is_immunity else Status.REFUTED, confidence=1.0,
                       proof={key: True, "scope": "closed-form model (OZ/raw), NON il bytecode deployato",
                              "bound": f"D in [0,{k}*v]", "method": "z3-UNSAT (continuo, non grid)"},
                       reason="z3: nessuna donazione nel bound rende l'attacco profittevole -> immune sul MODELLO a forma-chiusa",
                       script="smt_rounding.py")
