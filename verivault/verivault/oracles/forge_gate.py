"""
verivault.oracles.forge_gate — l'ORACOLO eseguibile (il fossato).

Esegue il gate BIDIREZIONALE via `forge test` su stato reale e ritorna un Verdict:
  - REFUTED  : esiste una donazione che rende l'attacco profittevole -> PoC reale (controesempio)
  - PASS     : nessuna donazione (fino a k*deposito) e' profittevole -> CERTIFICATO DI IMMUNITA parametrico
  - ABSTAIN  : il PoC non compila / il contratto non e' forkabile / fuori-scope (proxy senza impl)

DISCIPLINA-LICENZE: questo oracolo usa SOLO forge-std (MIT) + Solidity nostro (MIT). Gli engine
AGPL (medusa/halmos) si invocano, se servono, come SUBPROCESS non-modificati (vedi external/README.md).

STATO: il gate su MODELLI controllati (raw vs OZ) e' VALIDATO (forge/test/ImmunityCert.t.sol passa).
TODO (richiede setup di Daniel): gate su CONTRATTI REALI via mainnet-fork (vm.createSelectFork) — vedi
docs/ARCHITECTURE.md, sezione 'Stadio 4 su contratti reali'.
"""
from __future__ import annotations
import os, re, subprocess
from ..schemas import Claim, Verdict, Status
from .base import Oracle

FORGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "forge")
# RESULT <name> [offset=N] maxProfit=<int> [witness=<int>]  — witness = la donazione D* che esegue l'exploit
# RESULT <name> [VERDICT] [offset=N] maxProfit=<int> [witness=<int>] — il token-VERDETTO UPPERCASE (IMMUNE/VULN, formato
# BenchGate/ForkGate) e' opzionale e ignorato qui (lo decide il segno di maxProfit); compatibile con GeneralGate/ImmunityCert.
_RESULT = re.compile(r"RESULT\s+(\w+)(?:\s+[A-Z]+)?(?:\s+offset=(\d+))?\s+maxProfit=(-?\d+)(?:\s+witness=(\d+))?")


class ForgeGateOracle(Oracle):
    name = "forge_gate"

    def __init__(self, forge_dir: str = FORGE_DIR, timeout: int = 180):
        self.forge_dir = forge_dir
        self.timeout = timeout

    def _run(self, match_path: str) -> tuple[bool, str]:
        forge_bin = os.environ.get("FORGE_BIN", "forge")     # full-path override per PATH non-ereditato
        try:
            r = subprocess.run([forge_bin, "test", "--match-path", match_path, "-vv"],
                               cwd=self.forge_dir, capture_output=True, text=True, timeout=self.timeout)
            return True, (r.stdout or "") + "\n" + (r.stderr or "")
        except Exception as e:  # noqa
            return False, str(e)

    def decide(self, claim: Claim) -> Verdict:
        """claim.payload puo contenere {test_path}. Default: il certificato-immunita validato.
        Per contratti reali, l'orchestratore (Stadio 3) genera un test su fork e lo passa qui."""
        test_path = claim.payload.get("test_path", "test/ImmunityCert.t.sol")
        ran, out = self._run(test_path)
        if not ran:
            return Verdict(Status.ABSTAIN, reason=f"forge non eseguibile: {out[:120]}", script=test_path)
        if re.search(r"Compiler run failed|Error \(|could not compile", out):
            return Verdict(Status.ABSTAIN, reason="PoC non compila (fuori-scope o proxy senza impl)",
                           script=test_path, cost={"raw": out[-300:]})
        # estrai i profitti misurati (positivo = exploit reale; <=0 su tutta la griglia = immune) + witness D*
        profits, witnesses = {}, {}
        for m in _RESULT.finditer(out):
            key = m.group(1) + ("" if m.group(2) is None else f":offset{m.group(2)}")
            profits[key] = int(m.group(3))
            if m.group(4) is not None:
                witnesses[key] = int(m.group(4))
        if not profits:
            return Verdict(Status.ABSTAIN, reason="nessun RESULT dal gate (test non ha prodotto profitti)",
                           script=test_path)
        target = claim.payload.get("result_key")          # quale RESULT adjudica questo claim
        # FP=0 HARDENING (review): senza un result_key ESPLICITO non fare blind-max su tutte le RESULT.
        # Un harness multi-modello (es. ImmunityCert ha 'raw' con profit>0) darebbe una VULN SPURIA
        # scollegata dal target reale -> violazione di FP=0. Senza target univoco -> ABSTAIN dichiarato.
        if target is None:
            return Verdict(Status.ABSTAIN, script=test_path,
                           reason="result_key mancante: impossibile adjudicare un singolo target "
                                  "(blind-max su piu' RESULT -> FP) -> ABSTAIN")
        if target not in profits:
            return Verdict(Status.ABSTAIN, script=test_path,
                           reason=f"result_key {target!r} assente tra i RESULT del gate -> ABSTAIN")
        vals = [profits[target]]
        wit = witnesses.get(target)
        # FP=0 HARDENING (review): un maxProfit == type(int256).min (-2^255) significa che TUTTI i trial erano bloccati
        # (DoS sul deposit) -> l'attacco NON e' MAI stato ESEGUITO -> un IMMUNE qui sarebbe VACUO (falso-SAFE). ABSTAIN.
        if any(v <= -(2 ** 255) for v in vals):
            return Verdict(Status.ABSTAIN, script=test_path,
                           reason="verdetto VACUO: attacco mai eseguito (tutti i trial bloccati, sentinel int256.min) -> ABSTAIN")
        if claim.kind.endswith("immunity"):
            mx = max(vals)
            if mx <= 0:
                return Verdict(Status.PASS, confidence=1.0,
                               proof={"immunity_certificate": True, "max_attacker_profit_wei": mx,
                                      "all_profits": profits,
                                      # SCOPE-NAMING (anti-overclaim): il certificato nomina cosa copre e cosa NO
                                      "scope_covers": "donation/first-depositor inflation diretta, su questo bound D e questo blocco",
                                      "scope_excludes": ["oracle/price-manipulation cross-contract",
                                                          "ERC777/hook-reentrancy sul deposito",
                                                          "rounding-direction multi-step",
                                                          "interazioni cross-contract (composizione)"]},
                               reason="nessuna donazione e' profittevole entro il bound -> immune (scope dichiarato)", script=test_path)
            return Verdict(Status.REFUTED,
                           counterexample={"max_attacker_profit_wei": mx, "donation_witness_wei": wit, "profits": profits},
                           reason="esiste una donazione profittevole -> non immune", script=test_path)
        # default: claim di vulnerabilita -> PASS se exploit reale (profit>0)
        mx = max(vals)
        if mx > 0:
            return Verdict(Status.PASS, confidence=1.0,
                           counterexample={"attacker_profit_wei": mx, "donation_witness_wei": wit, "profits": profits},
                           reason="PoC eseguito: attaccante profitta -> VULN confermata", script=test_path)
        return Verdict(Status.REFUTED, reason="il PoC non profitta -> non confermato", script=test_path)
