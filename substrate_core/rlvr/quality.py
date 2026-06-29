"""substrate_core.rlvr.quality — il proxy di SEMPLICITA' (tier EMPIRICAL, MAI proven).

PERCHE' QUESTO MODULO E' "ONESTO E NON-SOUND" — la crepa #1 NON si chiude, si tier-tipa:
  Review avversariale 2026-06-07, VERIFICATA eseguendo greenery: il numero di stati del DFA MINIMO e'
  un INVARIANTE DI LINGUAGGIO -> due regex equivalenti hanno lo STESSO DFA minimo per definizione
  (a{10} e aaaaaaaaaa = 12 stati entrambe; a+ e aa* = 3). Quindi |DFA(R')| < |DFA(R)| e' UNSATISFIABLE
  tra equivalenti: NON puo' essere la leva di semplificazione. La semplificazione vive SOLO a livello
  SINTATTICO (forma-superficie / AST), che NON ha oracolo sound. Questo modulo e' quel proxy non-sound,
  ESEGUITO e DICHIARATO empirical. Non promuoverlo MAI a 'proven'.

Proxy scelto = `ast_nodes`: conteggio ricorsivo dei nodi del parse-tree greenery (Pattern/Conc/Mult).
VERIFICATO che ranka correttamente dove len(char) INVERTE:
  a=4  (((a)))=13  a{10}=4  aaaaaaaaaa=22  a|aa|aaa=16  a{1,3}=4  (a|a)=7  a+=4  aa*=6
(len(char): a{10}=5 < aaaaaaaaaa=10 -> INVERTE; ast_nodes non inverte.)
"""
from __future__ import annotations

from typing import Optional

import greenery
from greenery.rxelems import Pattern, Conc, Mult


def _node_count(x) -> int:
    """Conta i nodi del parse-tree greenery: Pattern -> Conc* -> Mult -> (Charclass | Pattern annidato)."""
    n = 1
    if isinstance(x, Pattern):
        for cc in x.concs:
            n += _node_count(cc)
    elif isinstance(x, Conc):
        for mm in x.mults:
            n += _node_count(mm)
    elif isinstance(x, Mult):
        n += _node_count(x.multiplicand)   # Charclass (foglia, +1) o Pattern annidato
    return n


def ast_nodes(R: str) -> Optional[int]:
    """Complessita' sintattica = nodi del parse-tree greenery. None se non parsabile (regex rotta/
    non-regolare): l'AST non e' definito -> il chiamante deve escludere il caso, non assegnargli reward."""
    try:
        return _node_count(greenery.parse(R))
    except Exception:  # noqa  (sintassi non valida, backref/lookaround, ecc.)
        return None


def syntactic_len(R: str) -> int:
    """Lunghezza grezza del pattern. SECONDARIA (loggata, non usata per il reward): len(char) INVERTE
    su quantificatori ripetuti -> tenuta solo come feature diagnostica, mai come gain."""
    return len(R)


def normal_form(R: str) -> Optional[str]:
    """Forma canonica-ish via greenery .reduce() (per il test di IDENTITA', non come target di training).
    None se non parsabile. NB: .reduce() non e' un normal-form unico garantito -> usato solo come guard."""
    try:
        return str(greenery.parse(R).reduce())
    except Exception:  # noqa
        return None


def is_identity(R: str, Rp: str) -> bool:
    """True se Rp e' la STESSA forma di R (copia o ridenominazione triviale equivalente): difesa esplicita
    contro la saturazione-identita' (crepa #1). Raw-equal OPPURE stessa forma ridotta greenery.
    NB: questo e' un guard ridondante con la pretesa 'ast_nodes strettamente minore' (un'identita' non
    riduce i nodi), ma reso esplicito per chiarezza/logging."""
    if R == Rp:
        return True
    nf_r, nf_rp = normal_form(R), normal_form(Rp)
    return nf_r is not None and nf_r == nf_rp


__all__ = ["ast_nodes", "syntactic_len", "normal_form", "is_identity"]
