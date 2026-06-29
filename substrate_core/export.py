"""substrate_core.export — STEP 2 (R6): la verita' come OGGETTO FISICO TRASPORTABILE, verificabile OFFLINE.

FASE 1 (questo modulo): il PAYLOAD fisico. Serializza CertGraph + blob del ProofStore (le inclusion-proof
mainnet) + le firme in UN file content-addressed compresso (.scar = substrate Content-Addressed aRchive).
Un verificatore STANDALONE lo carica e, con SOLA chiave + zero rete/DB/fiducia, conferma:
  (1) integrita': ogni cert ri-hashed == content_hash; firma valida;
  (2) provenance-gating: ogni arco/nodo coperto da un cert presente;
  (3) blob content-addressed: node_hash(blob)==CID;
  (4) RADICE Merkle ricalcolata dalle foglie == radice dichiarata (commette all'INTERO DAG);
  (5) RI-ESECUZIONE delle prove embedded (eth-mpt) -> il dato on-chain e' verificato OFFLINE, niente RPC.

Modello: CAR/IPLD (content-addressed, dedup, selective-disclosure) come CONTENITORE + DSSE/in-toto come
strato di FIRMA per-nodo. Complementari. (FASE 2: indice ADS Merkle-ordinato su `target` per query a completezza.)
"""
from __future__ import annotations

import gzip
import hashlib
import json
from typing import List, Optional

from .kernel import (Certificate, Claim, Verdict, Status, content_hash as _content_hash, verify_sig,
                     derive_pubkey, canonical_json, cert_from_dict)
from .statelight import verify_state_proof, node_hash
from .ads import build_index, query as ads_query, verify_query as ads_verify_query


def _target_entries(certs: dict):
    return [((env["certificate"]["claim"].get("target") or ""), ch) for ch, env in certs.items()]


_MLEAF, _MNODE = b"\x00", b"\x01"   # DOMAIN SEPARATION (CVE-2012-2459): foglia 0x00, nodo interno 0x01


def merkle_root(leaves: List[str]) -> str:
    """Radice Merkle binaria su foglie (content-hash hex), ORDINATE+dedup per determinismo. Commette all'insieme.
    DOMAIN SEPARATION (CVE-2012-2459): le foglie sono hashate col prefisso 0x00, i nodi interni con 0x01 -> l'hash
    di una foglia NON e' strutturalmente confondibile con quello di un nodo interno (niente second-preimage). Un
    nodo dispari viene PROMOSSO al livello superiore (NON duplicato) -> niente malleabilita' da duplicazione."""
    norm = sorted(set(leaves))
    for x in norm:                     # NIENTE scarto silenzioso: una foglia non valida va RIFIUTATA, non esclusa
        if not (isinstance(x, str) and len(x) == 64 and all(c in "0123456789abcdefABCDEF" for c in x)):
            raise ValueError("merkle_root: foglia non valida (atteso content-hash hex a 64 char): %r" % (x,))
    lv = [hashlib.sha256(_MLEAF + bytes.fromhex(x)).digest() for x in norm]
    if not lv:
        return hashlib.sha256(_MLEAF).hexdigest()
    while len(lv) > 1:
        nxt = []
        for i in range(0, len(lv), 2):
            if i + 1 < len(lv):
                nxt.append(hashlib.sha256(_MNODE + lv[i] + lv[i + 1]).digest())
            else:
                nxt.append(lv[i])   # nodo dispari PROMOSSO (no duplicazione -> no CVE-2012-2459)
        lv = nxt
    return lv[0].hex()


def _reconstruct(cd: dict) -> Certificate:
    vd = cd["verdict"]
    return Certificate(
        Claim(**cd["claim"]),
        Verdict(Status(vd["status"]), vd["executed"], vd.get("reason", ""), vd.get("witness", {}) or {},
                vd.get("reproduce", ""), vd.get("assurance", "none"), vd.get("coverage", {}) or {},
                vd.get("residual_risk"), vd.get("assurance_caveat", "")),
        cd.get("engine", ""), cd.get("stamp", ""))


def export_bundle(graph, *, proof_store=None, key: Optional[bytes] = None, name: str = "investigation",
                  embed_canonical: bool = False) -> dict:
    """Assembla il bundle CAR-shaped: certs (content-addressed) + grafo + blob-prova + RADICE che committa tutto.
    `embed_canonical`: incastona in ogni busta la stringa CANONICA esatta (i byte firmati) per la verifica
    CROSS-LINGUAGGIO nel browser (Pilastro 3) senza re-implementare il JSON di Python. `pubkey` (se key): la
    chiave pubblica dell'emittente, cosi' un terzo verifica l'AUTENTICITA' (non solo l'integrita' interna)."""
    certs = dict(getattr(graph, "_certs", {}))
    if embed_canonical:
        emb = {}
        for ch, env in certs.items():
            try:
                can = canonical_json(cert_from_dict(env["certificate"]))
            except Exception:  # noqa
                can = None
            emb[ch] = {**env, "canonical": can}
        certs = emb
    proofs = dict(getattr(proof_store, "blobs", {})) if proof_store else {}
    root = merkle_root(list(certs.keys()) + list(proofs.keys()))
    index_root = build_index(_target_entries(certs), axis="target")["root"]   # FASE 2: committa l'insieme COMPLETO
    return {
        "format": "scar/v1",
        "name": name,
        "root": root,
        "index_root": index_root,
        "pubkey": (derive_pubkey(key) if key else None),   # chiave pubblica emittente (per autenticazione terza)
        "n_blocks": len(certs) + len(proofs),
        "certs": certs,
        "graph": {"nodes": graph.nodes, "edges": graph.edges,
                  "dependents": {k: sorted(v) for k, v in getattr(graph, "_dependents", {}).items()}},
        "proofs": proofs,
    }


def save_bundle(bundle: dict, path: str) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, default=str)


def load_bundle(path: str) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def verify_bundle(bundle: dict, *, key: Optional[bytes] = None, pubkey: Optional[str] = None) -> dict:
    """IL VERIFICATORE STANDALONE OFFLINE: solo il bundle + la CHIAVE PUBBLICA. Niente rete, niente DB, niente
    fiducia, NESSUN potere di conio. `pubkey` = pubkey ATTESA dell'emittente (il modo onesto: l'auditor verifica
    l'AUTENTICITA'). `key` = seed (da cui si deriva la pubkey, comodita'). Se nessuno e' dato, ripiega sulla pubkey
    EMBEDDED in ogni busta (solo integrita'-interna: NON autentica l'emittente -> issuer_authenticated=False)."""
    vpub = pubkey if pubkey is not None else (derive_pubkey(key) if key else None)
    certs = bundle.get("certs", {}) or {}
    proofs = bundle.get("proofs", {}) or {}
    graph = bundle.get("graph", {}) or {}

    cert_ok, sig_ok = 0, 0
    cert_bad = []
    reexec = {"verified": 0, "failed": 0}
    for ch, env in certs.items():
        try:
            cert = _reconstruct(env["certificate"])
        except Exception:
            cert_bad.append(ch); continue
        if _content_hash(cert) != ch:                       # (1) integrita'
            cert_bad.append(ch); continue
        cert_ok += 1
        vp = vpub if vpub is not None else env.get("pubkey")   # attesa (autentica) o embedded (solo integrita')
        if env.get("sig") and vp and verify_sig(cert, env["sig"], vp):   # (1b) firma Ed25519
            sig_ok += 1
        # (5) ri-esecuzione delle prove embedded (eth-mpt) OFFLINE
        params = (env["certificate"]["claim"].get("params", {}) or {})
        sp, ctx = params.get("state_proof"), params.get("context")
        if sp and ctx and ctx.get("state_root"):
            ok = verify_state_proof(sp.get("proof_type", "merkle-demo"), {**sp, "state_root": ctx.get("state_root")})
            reexec["verified" if ok else "failed"] += 1

    prov_missing = sum(1 for e in graph.get("edges", []) if e.get("provenance") not in certs)  # (2)
    blob_bad = sum(1 for cid, node in proofs.items() if node_hash(node) != cid)                # (3)
    root_ok = merkle_root(list(certs.keys()) + list(proofs.keys())) == bundle.get("root")       # (4)
    index_ok = build_index(_target_entries(certs), axis="target")["root"] == bundle.get("index_root")  # (4b) ADS
    sig_all_ok = (cert_ok > 0 and sig_ok == cert_ok)        # ogni cert porta una firma VALIDA sotto la pubkey usata

    checks = {"certs_ok": cert_ok, "certs_bad": len(cert_bad), "sig_ok": sig_ok, "sig_all_ok": sig_all_ok,
              # issuer authenticated ONLY when an expected issuer pubkey/root was supplied AND every
              # signature verifies under it. Default offline path (embedded pubkey, no pre-trusted
              # root) -> False: the bundle is integrity-checked; the issuer is NOT authenticated.
              "issuer_authenticated": (vpub is not None) and sig_all_ok,
              "provenance_missing": prov_missing, "blob_bad": blob_bad, "root_ok": root_ok,
              "index_root_ok": index_ok, "embedded_proofs": reexec}
    intact = (not cert_bad and prov_missing == 0 and blob_bad == 0 and root_ok and index_ok
              and reexec["failed"] == 0 and sig_all_ok)
    return {"format": bundle.get("format"), "name": bundle.get("name"), "root": bundle.get("root"),
            "checks": checks, "intact": intact}


def query_bundle(bundle: dict, key) -> dict:
    """Query OFFLINE sul bundle con prova di COMPLETEZZA ANCORATA alla radice FIRMATA. L'indice e' ricostruito dai
    certs; ads.verify_query prova che nulla manca, ANCORANDO result.root all'index_root firmato del bundle (cosi'
    un avversario non puo' sostituire un SOTTOINSIEME forgiato con la sua radice auto-consistente)."""
    certs = bundle.get("certs", {}) or {}
    idx = build_index(_target_entries(certs), axis="target")
    res = ads_query(idx, key)
    signed_root = bundle.get("index_root")
    res["index_root_trusted"] = (idx["root"] == signed_root)
    res["completeness"] = ads_verify_query(res, expected_root=signed_root)   # ANCORATA: no sottoinsieme forgiato
    return res
