"""substrate_core.rlvr.reward — il REWARD non-saturabile dall'identita' (il cuore, risolve crepa #1).

Tre stadi sequenziali, con DUE tier MAI fusi:

  G1  SOUNDNESS (tier=proven, non-negoziabile): verify_equiv(R,R') deve dare CONFIRMED@proven.
      REFUTED/ABSTAIN/assurance!=proven  -> reward 0. Falso-proven STRUTTURALMENTE impossibile (l'oracolo).
  G2  ANTI-IDENTITA' LETTERALE (guard esplicito): R'==R  -> reward 0. (Ridondante con G3 ma chiaro.)
  G3  SEMPLICITA' (tier=EMPIRICAL, MAI proven): ast_nodes(R') < ast_nodes(R) -> reward 1, altrimenti 0.

CORREZIONE ONESTA alla spec della review (verificata eseguendo):
  Un de-parenthesize '(((a)))'->'a' RIDUCE i nodi AST 13->4: e' una SEMPLIFICAZIONE GENUINA e va PREMIATA
  (reward 1.0), NON trattata come identita'. Usare normal_form() per l'identita' sarebbe SBAGLIATO: ogni
  coppia equivalente ha la stessa forma ridotta (e' il senso dell'equivalenza), quindi normal_form-identity
  rigetterebbe OGNI rewrite valido. L'unica anti-saturazione corretta e' la decrescita STRETTA dei nodi AST.

Il reward complessivo eredita weakest(proven, empirical) = EMPIRICAL: lo dichiariamo, non lo gonfiamo.
La soundness copre "e' equivalente?"; la semplicita' resta un proxy non-sound. Limite = parte del prodotto.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .oracle import verify_equiv
from .quality import ast_nodes


def reward(R: str, Rp: str, *, key: Optional[bytes] = None) -> Dict[str, Any]:
    """Reward di UN rewrite R -> R'. Ritorna un dict ricco (reward + due tier separati + provenance),
    mai un solo scalare: il tier e' parte del segnale, non un di piu'."""
    out: Dict[str, Any] = {
        "R": R, "Rp": Rp, "reward": 0.0,
        "tier_sound": "none", "tier_quality": "none", "tier": "none",
        "gates": {"G1_sound": False, "G2_not_identity": False, "G3_simpler": False},
        "status": None, "assurance": None, "witness": None,
        "ast_R": None, "ast_Rp": None, "content_hash": None, "reason": "",
    }

    # G1 — SOUNDNESS GATE
    v = verify_equiv(R, Rp, key=key)
    out["status"], out["assurance"] = v["status"], v["assurance"]
    out["witness"], out["content_hash"] = v["witness"], v["content_hash"]
    if not (v["status"] == "CONFIRMED" and v["assurance"] == "proven"):
        out["reason"] = f"G1 fail: {v['status']}/{v['assurance']} (non CONFIRMED@proven)"
        return out
    out["gates"]["G1_sound"] = True
    out["tier_sound"] = "proven"

    # G2 — ANTI-IDENTITA' LETTERALE (guard esplicito; un'identita' non riduce i nodi -> anche G3 la prende)
    if R == Rp:
        out["reason"] = "G2 fail: R'==R identita' letterale (saturazione crepa #1)"
        return out
    out["gates"]["G2_not_identity"] = True

    # G3 — SEMPLICITA' SINTATTICA (EMPIRICAL): nodi AST strettamente minori
    na_r, na_rp = ast_nodes(R), ast_nodes(Rp)
    out["ast_R"], out["ast_Rp"] = na_r, na_rp
    if na_r is None or na_rp is None:
        out["reason"] = "G3 indeterminato: AST non calcolabile (regex non parsabile)"
        return out
    out["tier_quality"] = "empirical"
    if na_rp < na_r:
        out["gates"]["G3_simpler"] = True
        out["reward"] = 1.0
        out["tier"] = "empirical"   # weakest(proven, empirical) — onesto, mai 'proven'
        out["reason"] = f"OK: equivalente@proven E piu' semplice (AST {na_r}->{na_rp})"
    else:
        out["tier"] = "empirical"
        out["reason"] = f"G3 fail: equivalente ma NON piu' semplice (AST {na_r}->{na_rp})"
    return out


__all__ = ["reward"]
