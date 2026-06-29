"""substrate_core.semantic_ledger — SEMANTIC LEDGER: knowledge-base indirizzata per IDENTITA' COMPORTAMENTALE.

Due stadi (l'unica forma onesta):
  1. BUCKETER CANDIDATO (cheap): semantic_hash(R) raggruppa le regex per comportamento-candidato.
  2. GIUDICE SOUND: su ogni collisione di bucket, `regex_equiv` ADJUDICA. CONFIRMED@proven -> collasso PROVATO,
     firmato e ingerito nel CertGraph write-gated. ABSTAIN/REFUTED -> OVER-COLLAPSE: DEMOTATO a near-miss,
     LOGGATO col witness eseguito, MAI coniato PROVEN. (E' il caso (.*) dove greenery e Python-re divergono sul \\n.)

Proprieta': zero falsi-proven per costruzione (solo i CONFIRMED@proven entrano nel grafo). L'hash imperfetto
costa solo RECALL (equivalenze mancate), mai soundness. Lookup con prova di completezza (ads) + export .scar
verificabile OFFLINE. Tier: equivalenza=PROVEN (oracle-bound + re.fullmatch indipendente sui REFUTED);
"rappresentante piu' semplice"=EMPIRICAL (ast_nodes). Vedi [[semantic_hash]], [[verified_regex_kb]].
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import ads, derive_pubkey, verify, Claim
from .cert_graph import CertGraph
from .export import export_bundle, save_bundle, verify_bundle, load_bundle
from .semantic_hash import semantic_hash
from .domains import regex_equiv  # noqa: F401  (registra il dominio: il giudice)


def _ast_nodes(R: str) -> int:
    try:
        from .rlvr.quality import ast_nodes
        n = ast_nodes(R)
        return n if n is not None else len(R)
    except Exception:  # noqa
        return len(R)


class SemanticLedger:
    def __init__(self, key: bytes):
        self.key = key
        self.pub = derive_pubkey(key)
        self.graph = CertGraph(pubkey=self.pub)          # write-gated: solo certificati firmati entrano
        self.reps: Dict[str, str] = {}                   # semantic_hash -> regex rappresentante (AST-minimo)
        self.members: Dict[str, List[str]] = {}          # semantic_hash -> regex distinte provate equivalenti
        self.near_misses: List[Dict[str, Any]] = []      # over-collapse: stesso hash, giudice DISACCORDA
        self.proven_collapses = 0
        self.ingested = 0
        self.out_of_fragment = 0

    def _adjudicate(self, r1: str, r2: str) -> Dict[str, Any]:
        return verify(Claim(domain="regex_equiv", target=f"collapse:{r1}|{r2}", kind="equivalence",
                            params={"r1": r1, "r2": r2}), key=self.key)

    def ingest(self, regex: str) -> Tuple[str, Optional[str]]:
        """Inserisce una regex. Ritorna (esito, hash). esito ∈ {out_of_fragment, new_class, dup, collapse_proven,
        over_collapse_demoted}."""
        h = semantic_hash(regex)
        if h is None:
            self.out_of_fragment += 1
            return ("out_of_fragment", None)
        if h not in self.reps:
            self.reps[h] = regex
            self.members[h] = [regex]
            self.ingested += 1
            return ("new_class", h)
        if regex in self.members[h]:
            return ("dup", h)
        rep = self.reps[h]
        env = self._adjudicate(regex, rep)                # IL GIUDICE SOUND decide il collasso
        v = env["certificate"]["verdict"]
        if v["status"] == "CONFIRMED" and v["assurance"] == "proven":
            self.graph.ingest(env)                        # collasso PROVATO -> firmato nel grafo
            self.members[h].append(regex)
            self.proven_collapses += 1
            if _ast_nodes(regex) < _ast_nodes(rep):       # rappresentante = forma AST-minima (proxy EMPIRICAL)
                self.reps[h] = regex
            return ("collapse_proven", h)
        # OVER-COLLAPSE: stesso hash ma il giudice non conferma -> DEMOTA, non coniare (il caso (.*)/\\n)
        self.near_misses.append({"regex": regex, "rep": rep, "status": v["status"],
                                 "witness": (v.get("witness", {}) or {}).get("distinguishing_string")})
        return ("over_collapse_demoted", h)

    def multi_syntax_classes(self) -> int:
        return sum(1 for ms in self.members.values() if len(ms) >= 2)

    def lookup(self, regex: str) -> Dict[str, Any]:
        """Cerca la classe comportamentale di `regex` + PROVA di completezza (nulla nascosto), ancorata alla radice."""
        h = semantic_hash(regex)
        idx = ads.build_index([(hh, rep) for hh, rep in self.reps.items()])
        res = ads.query(idx, h if h is not None else "###out-of-fragment###")
        ver = ads.verify_query(res, expected_root=idx["root"])
        return {"hash": h, "representative": self.reps.get(h), "completeness": ver}

    def export_scar(self, path: str) -> dict:
        bundle = export_bundle(self.graph, key=self.key, name="semantic-ledger", embed_canonical=True)
        save_bundle(bundle, path)
        return bundle

    def stats(self) -> Dict[str, Any]:
        return {"ingested_in_fragment": self.ingested, "out_of_fragment": self.out_of_fragment,
                "behavioral_classes": len(self.reps), "multi_syntax_classes": self.multi_syntax_classes(),
                "proven_collapses": self.proven_collapses, "over_collapses_demoted": len(self.near_misses),
                "graph_certs": len(self.graph._certs)}


__all__ = ["SemanticLedger"]
