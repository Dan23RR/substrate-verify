"""substrate_core.cert_graph — GRAFO DI CERTIFICATI provenance-gated (la spina dorsale della memoria).

Critica #3, punto 1 (il passo SICURO, non intacca il determinismo del kernel): trasforma certificati isolati
in un grafo connesso. L'INVARIANTE che lo rende un "Palantir proof-carrying":

    OGNI nodo e OGNI arco porta il content_hash del certificato del kernel che l'ha creato.
    Non si puo' scrivere un nodo/arco SENZA un certificato di provenienza.
    -> ogni relazione visualizzata e' crittograficamente legata a un'esecuzione verificata.

Il grafo e' READ-OPEN, WRITE-GATED-AI-CERTIFICATI: il futuro agente non-fidato puo' interrogarlo liberamente,
ma non puo' coniare qui nulla che il kernel non abbia firmato. `ingest(envelope)` e' l'UNICO writer pubblico.

Backend-agnostic, embeddable (pure-Python, JSON). Si rimpiazza con Postgres+AGE piu' avanti: invariante e API restano.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from typing import Dict, List, Optional

from .kernel import content_hash as _hash, Certificate, Claim, Verdict, Status, verify_sig, derive_pubkey, cert_from_dict


class ProvenanceError(Exception):
    """Tentativo di scrivere nel grafo senza un certificato di provenienza -> RIFIUTATO."""


class CertGraph:
    def __init__(self, pubkey: Optional[str] = None, allow_unsigned: bool = False):
        self.pubkey = pubkey                 # pubkey FIDATA: se settata, ingest verifica l'IDENTITA' dell'emittente
        # default (recon 2026-06-05): anche SENZA pubkey fidata il grafo verifica la firma INCASTONATA -> rifiuta
        # non-firmati e corpi manomessi (la vecchia firma non torna sull'hash ricomputato). allow_unsigned=True
        # ripristina la modalita' legacy SOLO-INTEGRITA' (nessuna garanzia d'autenticita') in modo esplicito.
        self.allow_unsigned = allow_unsigned
        self.nodes: Dict[str, dict] = {}     # key -> {key,type,attrs,provenance:[hash]}
        self.edges: List[dict] = []          # {src,dst,type,attrs,provenance}
        self._certs: Dict[str, dict] = {}    # content_hash -> busta (la prova ri-eseguibile)
        self._dependents: Dict[str, set] = {}  # cert_hash -> set(cert che DIPENDONO da esso) per la cascata

    # ---- scrittura GATED (privata): senza provenance -> eccezione ----
    def _node(self, key: str, ntype: str, provenance: str, **attrs):
        if not provenance:
            raise ProvenanceError(f"nodo {key!r} senza provenance (content_hash) -> RIFIUTATO")
        n = self.nodes.setdefault(key, {"key": key, "type": ntype, "attrs": {}, "provenance": []})
        n["attrs"].update({k: v for k, v in attrs.items() if v is not None})
        if provenance not in n["provenance"]:
            n["provenance"].append(provenance)
        return key

    def _edge(self, src: str, dst: str, etype: str, provenance: str, **attrs):
        if not provenance:
            raise ProvenanceError(f"arco {src}->{dst} senza provenance -> RIFIUTATO")
        self.edges.append({"src": src, "dst": dst, "type": etype,
                           "attrs": {k: v for k, v in attrs.items() if v is not None}, "provenance": provenance})

    # ---- l'UNICO writer pubblico: un certificato del kernel ----
    def ingest(self, envelope: dict) -> str:
        ch = envelope.get("content_hash")
        if not ch:
            raise ProvenanceError("busta senza content_hash -> non ingeribile")
        # WRITE-GATE CRITTOGRAFICO: il grafo si DIFENDE prima di toccare lo stato. (1) Ricomputa il content_hash
        # dal certificato (un corpo manomesso non torna). (2) Se configurato con una pubkey FIDATA, VERIFICA la
        # firma Ed25519. Un processo locale compromesso o un LLM che bypassa il seam NON puo' avvelenare la memoria.
        try:
            _cert = cert_from_dict(envelope["certificate"])
        except Exception as e:  # noqa
            raise ProvenanceError(f"busta non ricostruibile -> RIFIUTATA ({type(e).__name__})")
        if _hash(_cert) != ch:
            raise ProvenanceError("content_hash NON combacia col certificato -> busta manomessa, RIFIUTATA")
        sig, emb_pub = envelope.get("sig"), envelope.get("pubkey")
        if self.pubkey is not None:
            # grafo FIDATO: la firma deve verificare sotto la pubkey ATTESA (identita' dell'emittente).
            if not verify_sig(_cert, sig, self.pubkey):
                raise ProvenanceError("firma Ed25519 non valida sotto la pubkey fidata del grafo -> RIFIUTATA (anti-poisoning)")
        elif not self.allow_unsigned:
            # grafo di DEFAULT: autenticita' self-consistent. Rifiuta i NON-firmati e i corpi MANOMESSI (la firma
            # incastonata non verifica piu' sull'hash ricomputato). Senza pubkey fidata non garantisce l'IDENTITA',
            # ma garantisce firma-presente + non-manomissione. (allow_unsigned=True -> vecchia modalita' integrita'.)
            if not sig or not emb_pub:
                raise ProvenanceError("busta NON firmata -> RIFIUTATA dal grafo di default "
                                      "(usa CertGraph(allow_unsigned=True) per la modalita' solo-integrita')")
            if not verify_sig(_cert, sig, emb_pub):
                raise ProvenanceError("firma Ed25519 non valida sotto la pubkey incastonata -> RIFIUTATA (corpo manomesso/firma invalida)")
        self._certs[ch] = envelope
        cert = envelope["certificate"]
        claim = cert["claim"]
        v = cert["verdict"]
        dom = claim.get("domain")
        kind = claim.get("kind", "")
        target = claim.get("target")
        params = claim.get("params", {}) or {}
        st, asr = v.get("status"), v.get("assurance", "none")

        # DIPENDENZE per l'invalidazione a cascata: questo cert ha ereditato un input da un altro? (passaggio di testimone)
        inp = params.get("input_from")
        if inp:
            self._dependents.setdefault(inp, set()).add(ch)
            self._node(f"cert:{ch[:12]}", "certificate", ch, status=st, assurance=asr)
            self._node(f"cert:{inp[:12]}", "certificate", ch)
            self._edge(f"cert:{ch[:12]}", f"cert:{inp[:12]}", "depends-on", ch)

        if dom == "entity_probe":
            # IL TIPO viene SOLO da un probe ESEGUITO (chiude la breccia R1): mai da un'etichetta.
            ent = f"entity:{target}"
            if st == "CONFIRMED":
                etype = (v.get("coverage", {}) or {}).get("entity_type") or kind.split(":")[-1]
                self._node(ent, "entity", ch, entity_type=etype, type_assurance=asr, type_provenance=ch)
            else:
                self._node(ent, "entity", ch)   # probe inconcludente -> l'entita' resta UNTYPED (onesto)
            return ch
        if dom == "investigation":
            seed = f"entity:{target}"
            self._node(seed, "entity", ch, asserted_role="investigation-seed")
            for sink, amt in (params.get("sinks", {}) or {}).items():
                # 'sink'/'mixer' sono LEAD dell'investigatore, NON tipi verificati: servono un entity_probe per diventare TIPO
                self._node(f"entity:{sink}", "entity", ch, asserted_role="sink", role_status="LEAD-non-verificato")
                self._edge(seed, f"entity:{sink}", "traced", ch, amount=amt, status=st, assurance=asr)
            for obs, amt in (params.get("obscured", {}) or {}).items():
                self._node(f"entity:{obs}", "entity", ch, asserted_role="mixer", role_status="LEAD-non-verificato")
                self._edge(seed, f"entity:{obs}", "obscured", ch, amount=amt, status="ABSTAIN", assurance="none")
            return ch
        if dom == "composite":
            sysn = f"system:{ch[:12]}"
            self._node(sysn, "system", ch, verdict=st, assurance=asr, kind=kind)
            for child in (params.get("child_hashes", []) or []):
                self._node(f"cert:{child[:12]}", "certificate", ch)
                self._edge(sysn, f"cert:{child[:12]}", "composed-of", ch)
                self._dependents.setdefault(child, set()).add(ch)   # il sistema dipende dai figli -> cascata
            return ch
        if dom == "flowtrace":
            frm, _, to = str(target).partition("->")
            to = to or frm
            self._node(f"entity:{frm}", "entity", ch)
            self._node(f"entity:{to}", "entity", ch)
            self._edge(f"entity:{frm}", f"entity:{to}", "flow", ch, status=st, assurance=asr,
                       ref=(v.get("witness", {}) or {}).get("ref"))
            return ch
        # dominio generico (erc4626, pyprop, ...): nodo-target + nodo-verdetto stampato col content_hash
        tnode = f"target:{os.path.basename(str(target))}"
        self._node(tnode, "target", ch, domain=dom, kind=kind)
        vnode = f"verdict:{ch[:12]}"
        self._node(vnode, "verdict", ch, status=st, assurance=asr, residual_risk=v.get("residual_risk"))
        self._edge(tnode, vnode, "has-verdict", ch, status=st, assurance=asr)
        return ch

    # ---- query (READ-OPEN) ----
    def neighbors(self, key: str) -> List[dict]:
        return [e for e in self.edges if e["src"] == key or e["dst"] == key]

    def nodes_by_type(self, t: str) -> List[dict]:
        return [n for n in self.nodes.values() if n["type"] == t]

    def typed_entities(self) -> List[dict]:
        """Solo le entita' il cui TIPO e' backed da un cert entity_probe ESEGUITO (mai da un'etichetta)."""
        return [n for n in self.nodes.values() if "entity_type" in n["attrs"]]

    def edges_by_status(self, status: str) -> List[dict]:
        return [e for e in self.edges if e["attrs"].get("status") == status]

    def provenance(self, content_hash: str) -> Optional[dict]:
        """Restituisce il certificato (ri-eseguibile) dietro un nodo/arco: la prova della relazione."""
        return self._certs.get(content_hash)

    def invalidate(self, content_hash: str) -> dict:
        """Invalidazione a CASCATA: un cert cambia/diventa REFUTED (es. zero-day) -> tutti i cert che ne
        DIPENDONO (via input_from o composizione, TRANSITIVAMENTE) vanno ri-valutati. Ritorna i dipendenti.
        NB: invalida = marca da-ri-eseguire; non conia verita' (il ricalcolo passa per il kernel)."""
        seen, stack, out = set(), [content_hash], []
        while stack:
            h = stack.pop()
            for dep in self._dependents.get(h, ()):
                if dep not in seen:
                    seen.add(dep); out.append(dep); stack.append(dep)
        return {"trigger": content_hash, "invalidated": out, "count": len(out)}

    def decay(self, changed_targets) -> dict:
        """Decadimento TEMPORALE reattivo (TOCTOU). A ogni nuovo blocco col suo state-diff, i certificati
        CONFIRMED su uno STATO il cui TARGET e' tra i changed_targets decadono da LIVE a STALE — NON a REFUTED
        (la verita' @block N regge; e' stale per il PRESENTE) — e innescano la cascata sui dipendenti present-tense.
        I cert ETERNI (senza context, es. file-codice) NON decadono mai."""
        changed = set(changed_targets)
        stale = []
        for ch, env in self._certs.items():
            cert = env["certificate"]; claim = cert["claim"]; vd = cert["verdict"]
            ctx = (claim.get("params", {}) or {}).get("context")
            if ctx is None:
                continue                                   # eterno -> immune al decadimento
            if vd.get("status") == "CONFIRMED" and claim.get("target") in changed:
                stale.append(ch)
        cascade, stack = set(), list(stale)
        while stack:
            h = stack.pop()
            for dep in self._dependents.get(h, ()):
                if dep not in cascade:
                    cascade.add(dep); stack.append(dep)
        return {"changed_targets": sorted(changed), "stale": stale,
                "cascade_invalidated": sorted(cascade), "note": "STALE (storico), non REFUTED: ri-eseguibile @ blocco originale"}

    # ---- integrita' PROOF-CARRYING: ogni nodo/arco coperto da un cert valido (hash + firma) ----
    def verify_integrity(self, pubkey: Optional[str] = None, key: Optional[bytes] = None) -> dict:
        pub = pubkey if pubkey is not None else (derive_pubkey(key) if key else None)
        missing = []
        for n in self.nodes.values():
            for h in n["provenance"]:
                if h not in self._certs:
                    missing.append(("node", n["key"], h))
        for e in self.edges:
            if e["provenance"] not in self._certs:
                missing.append(("edge", f"{e['src']}->{e['dst']}", e["provenance"]))
        ok = bad = 0
        for ch, env in self._certs.items():
            try:
                cd = env["certificate"]; vd = cd["verdict"]
                cert = Certificate(
                    Claim(**cd["claim"]),
                    Verdict(Status(vd["status"]), vd["executed"], vd.get("reason", ""), vd.get("witness", {}) or {},
                            vd.get("reproduce", ""), vd.get("assurance", "none"), vd.get("coverage", {}) or {},
                            vd.get("residual_risk"), vd.get("assurance_caveat", "")),
                    cd.get("engine", ""), cd.get("stamp", ""))
                if _hash(cert) != ch:
                    bad += 1; continue
                if pub and env.get("sig") and not verify_sig(cert, env["sig"], pub):
                    bad += 1; continue
                ok += 1
            except Exception:  # noqa
                bad += 1
        return {"nodes": len(self.nodes), "edges": len(self.edges), "certs": len(self._certs),
                "provenance_missing": missing, "certs_ok": ok, "certs_bad": bad,
                "intact": (not missing and bad == 0)}

    def stats(self) -> dict:
        return {"nodes": len(self.nodes), "edges": len(self.edges), "certs": len(self._certs),
                "node_types": dict(Counter(n["type"] for n in self.nodes.values())),
                "edge_types": dict(Counter(e["type"] for e in self.edges))}

    def save(self, path: str):
        """Persistenza con scrittura ATOMICA (tmp + os.replace: nessun file mezzo-scritto se il processo muore).
        Persiste anche la pubkey FIDATA, cosi' il grafo ricaricato resta write-gated."""
        data = {"pubkey": self.pubkey, "allow_unsigned": self.allow_unsigned,
                "nodes": self.nodes, "edges": self.edges, "certs": self._certs,
                "dependents": {k: sorted(v) for k, v in self._dependents.items()}}
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp, path)   # rename atomico

    @classmethod
    def load(cls, path: str, *, verify: bool = True, pubkey: Optional[str] = None, allow_unsigned: bool = False):
        """Carica un grafo persistito. Il DISCO e' una superficie d'attacco: con verify=True (default) load NON si
        fida del JSON — RICOSTRUISCE nodi/archi RE-INGERENDO ogni busta (ri-verifica hash+firma via il write-gate) e
        poi CONFRONTA col contenuto su disco: qualunque divergenza (corpo manomesso, byte corrotto, firma forgiata,
        nodo/arco alterato) -> ProvenanceError. La pubkey fidata (persistita o passata) sopravvive."""
        # TRUST ANCHOR DAL CHIAMANTE, MAI DAL FILE (recon 2026-06-05): pubkey/allow_unsigned PERSISTITE sono
        # INFORMATIVE e NON-fidate (chi controlla il file le cambierebbe per declassare identita' -> sola-integrita').
        # L'identita' (only-this-issuer) si verifica SOLO contro la `pubkey` passata dal chiamante; senza, integrity-only
        # per scelta ESPLICITA (niente downgrade silenzioso via lo strip della pubkey dal file).
        d = json.load(open(path, encoding="utf-8"))
        g = cls(pubkey=pubkey, allow_unsigned=bool(allow_unsigned))
        g._declared_pubkey = d.get("pubkey")   # informativo: cosa dichiarava il file (per audit/confronto), non fidato
        if not verify:
            g.nodes = d.get("nodes", {}); g.edges = d.get("edges", [])
            g._certs = d.get("certs", {}) or {}
            g._dependents = {k: set(v) for k, v in d.get("dependents", {}).items()}
            return g
        certs = d.get("certs", {}) or {}
        for ch, env in certs.items():
            if env.get("content_hash") != ch:
                raise ProvenanceError(f"chiave _certs {str(ch)[:12]} != content_hash della busta -> file manomesso")
            if g.ingest(env) != ch:   # re-ingest: write-gate ri-verifica hash+firma e RIGENERA nodi/archi
                raise ProvenanceError("re-ingest ha prodotto un hash diverso -> file manomesso")
        disk_deps = {k: set(v) for k, v in d.get("dependents", {}).items()}
        if g.nodes != d.get("nodes", {}) or g.edges != d.get("edges", []) or g._dependents != disk_deps:
            raise ProvenanceError("nodi/archi/dipendenze su disco NON coerenti coi certificati rigenerati -> file manomesso")
        return g
