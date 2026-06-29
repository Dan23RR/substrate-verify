"""substrate_core.netacl_ledger — il SEMANTIC LEDGER esteso al 2o DOMINIO (firewall/ACL).

Stessa disciplina a due stadi di semantic_ledger.py, parametrizzata su (bucketer, giudice):
  bucketer = netacl_semantic_hash (cheap, recall-only);  giudice = dominio 'netacl_equiv' (Z3, sound).
Un collasso entra nel CertGraph write-gated SOLO se il giudice da CONFIRMED@proven; un over-collapse (stesso
fingerprint ma giudice ABSTAIN/REFUTED) e' DEMOTATO a near-miss col PACCHETTO eseguito, MAI coniato.

Dimostra che il substrato e' GENUINAMENTE multi-dominio: lo STESSO ledger firmato/portabile/completezza-provabile/
auto-risanante ora indirizza fatti di equivalenza-firewall per IDENTITA' COMPORTAMENTALE PROVATA. Vedi
[[semantic_ledger]], [[netacl_hash]]. Novita' = il LEDGER (Header-Space-Analysis/Margrave/Zelkova decidono gia').
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import ads, derive_pubkey, verify, Claim
from .cert_graph import CertGraph
from .export import export_bundle, save_bundle
from .netacl_hash import netacl_semantic_hash
from .domains import netacl_equiv  # noqa: F401  (registra il giudice)


class NetAclLedger:
    def __init__(self, key: bytes):
        self.key = key
        self.pub = derive_pubkey(key)
        self.graph = CertGraph(pubkey=self.pub)
        self.reps: Dict[str, Dict[str, Any]] = {}        # hash -> {name, ruleset, fields, default}
        self.members: Dict[str, List[str]] = {}          # hash -> nomi delle ACL provate equivalenti
        self.near_misses: List[Dict[str, Any]] = []
        self.proven_collapses = 0
        self.classes = 0

    def _adjudicate(self, a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
        return verify(Claim(domain="netacl_equiv", target=f"{a['name']}|{b['name']}", kind="equivalence",
                            params={"rulesetA": a["ruleset"], "rulesetB": b["ruleset"],
                                    "fields": a["fields"], "defaultA": a["default"], "defaultB": b["default"]}), key=self.key)

    def ingest(self, name: str, ruleset, fields: Dict[str, int], default: str = "DENY") -> Tuple[str, Optional[str]]:
        item = {"name": name, "ruleset": ruleset, "fields": fields, "default": default}
        h = netacl_semantic_hash(ruleset, fields, default)
        if h is None:
            return ("unbucketable", None)
        if h not in self.reps:
            self.reps[h] = item
            self.members[h] = [name]
            self.classes += 1
            return ("new_class", h)
        if name in self.members[h]:
            return ("dup", h)
        rep = self.reps[h]
        if rep["fields"] != fields or rep["default"] != default:
            return ("schema_mismatch", h)               # stesso fingerprint ma schema diverso -> non comparabile
        env = self._adjudicate(item, rep)               # IL GIUDICE Z3 decide il collasso
        v = env["certificate"]["verdict"]
        if v["status"] == "CONFIRMED" and v["assurance"] == "proven":
            self.graph.ingest(env)                       # collasso PROVATO -> firmato nel grafo write-gated
            self.members[h].append(name)
            self.proven_collapses += 1
            return ("collapse_proven", h)
        # OVER-COLLAPSE: stesso fingerprint ma il giudice non conferma -> DEMOTA col pacchetto, MAI coniare
        self.near_misses.append({"name": name, "rep": rep["name"], "status": v["status"],
                                 "packet": (v.get("witness", {}) or {}).get("packet")})
        return ("over_collapse_demoted", h)

    def multi_member_classes(self) -> int:
        return sum(1 for ms in self.members.values() if len(ms) >= 2)

    def lookup(self, ruleset, fields: Dict[str, int], default: str = "DENY") -> Dict[str, Any]:
        h = netacl_semantic_hash(ruleset, fields, default)
        idx = ads.build_index([(hh, it["name"]) for hh, it in self.reps.items()])
        res = ads.query(idx, h if h is not None else "###unbucketable###")
        return {"hash": h, "representative": (self.reps.get(h) or {}).get("name"),
                "completeness": ads.verify_query(res, expected_root=idx["root"])}

    def export_scar(self, path: str) -> dict:
        bundle = export_bundle(self.graph, key=self.key, name="netacl-ledger", embed_canonical=True)
        save_bundle(bundle, path)
        return bundle

    def stats(self) -> Dict[str, Any]:
        return {"classes": self.classes, "multi_member_classes": self.multi_member_classes(),
                "proven_collapses": self.proven_collapses, "over_collapses_demoted": len(self.near_misses),
                "graph_certs": len(self.graph._certs)}


__all__ = ["NetAclLedger"]
