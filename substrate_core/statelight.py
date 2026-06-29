"""substrate_core.statelight — il KERNEL come LIGHT CLIENT (chiude il buco dell'oracolo RPC).

Il kernel NON fa chiamate RPC e NON si fida del nodo. Il prover (untrusted) deve fornire una INCLUSION PROOF
(Merkle/MPT/Verkle) che il dato (bytecode / storage slot) appartiene allo state_root DICHIARATO nel contesto.
Il kernel la VERIFICA offline: ricompone la radice dal percorso; se non combacia con lo state_root pinnato
-> ABSTAIN(invalid-data-proof). La verita' dipende dalla matematica nel JSON, non dall'esistenza della chain.

PERFORMANCE: le prove sono pesanti e SI SOVRAPPONGONO (al solito blocco condividono il trie alto). Il
ProofStore content-addressed salva ogni nodo-prova UNA VOLTA (per hash); il witness porta i CID, non i nodi
grezzi -> crescita SUB-LINEARE, export = sub-DAG + solo i blob raggiungibili. (Astrazione MPT/Verkle: il
principio — 'ricomponi la radice, confrontala con quella committata' — e' identico per ogni formato di proof.)
"""
from __future__ import annotations

import hashlib
import json
from typing import List, Optional, Tuple


def _h(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _leaf_hash(leaf_value) -> str:
    return _h(json.dumps(leaf_value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8"))


def node_hash(node: dict) -> str:
    return _h(json.dumps(node, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8"))


def verify_inclusion(state_root: Optional[str], leaf_value, proof_path: List[dict]) -> bool:
    """VERIFICA offline (il kernel come light client): ricompone la radice dal leaf lungo proof_path e la
    confronta con lo state_root committato. proof_path = lista di {sibling, dir}. False se manca o non combacia."""
    if not state_root or leaf_value is None:
        return False
    cur = _leaf_hash(leaf_value)
    for step in (proof_path or []):
        sib = step.get("sibling", "")
        cur = _h((cur + sib).encode()) if step.get("dir") == "right" else _h((sib + cur).encode())
    return cur == state_root


def build_proof(leaf_value, siblings: List[str]) -> Tuple[str, List[dict]]:
    """Helper (test/demo): dato un leaf + sibling-hash, costruisce il path e CALCOLA la radice risultante.
    Ritorna (state_root, proof_path). In produzione il prover ESTRAE questi nodi dal nodo RPC e li presenta."""
    cur = _leaf_hash(leaf_value)
    path = []
    for i, sib in enumerate(siblings):
        d = "right" if i % 2 == 0 else "left"
        path.append({"sibling": sib, "dir": d})
        cur = _h((cur + sib).encode()) if d == "right" else _h((sib + cur).encode())
    return cur, path


class ProofStore:
    """Store CONTENT-ADDRESSED dei nodi-prova: dedup per hash. Il witness referenzia i CID, non i nodi grezzi.
    I nodi del trie-alto, condivisi da molte prove allo stesso blocco, sono salvati UNA volta -> sub-lineare."""

    def __init__(self):
        self.blobs: dict = {}   # cid -> nodo

    def put(self, node: dict) -> str:
        cid = node_hash(node)
        self.blobs[cid] = node
        return cid

    def put_path(self, proof_path: List[dict]) -> List[str]:
        return [self.put(step) for step in proof_path]   # ritorna i CID -> witness LEGGERO

    def get(self, cid: str) -> Optional[dict]:
        return self.blobs.get(cid)

    def materialize(self, cids: List[str]) -> List[dict]:
        return [self.blobs[c] for c in cids if c in self.blobs]

    def stats(self) -> dict:
        return {"unique_nodes": len(self.blobs)}


# ------------------------------------------------------------------------------------------------------
# VERIFICATORI DI PROVA PLUGGABLE per `proof_type` (niente hand-rolling di crittografia; niente finzioni).
#   merkle-demo : albero binario DIDATTICO -> NON mainnet (dimostra solo il principio del seam).
#   eth-mpt     : Ethereum Modified Merkle Patricia Trie REALE (py-trie battle-tested) -> mainnet.
#   verkle      : futuro (slot riservato).
# ------------------------------------------------------------------------------------------------------

def _b(h):
    if isinstance(h, str):
        return bytes.fromhex(h[2:] if h.startswith("0x") else h)
    return bytes(h)


def verify_eth_mpt(state_root, address, account_proof, expected=None) -> bool:
    """REALE Ethereum MPT (py-trie, battle-tested, NON hand-rolled). Verifica OFFLINE che l'account-proof
    dimostri l'account ad `address` contro `state_root`. `expected` (opz.) LEGA il valore (nonce/balance/hashes)."""
    try:
        import rlp
        from trie import HexaryTrie
        from eth_utils import keccak, to_bytes
    except Exception:
        return False
    try:
        sr = _b(state_root)
        key = keccak(to_bytes(hexstr=address))
        nodes = [rlp.decode(_b(n)) for n in (account_proof or [])]
        val = HexaryTrie.get_from_proof(sr, key, nodes)
    except Exception:
        return False
    if expected:
        try:
            want = rlp.encode([int(expected["nonce"]), int(expected["balance"]),
                               _b(expected["storage_hash"]), _b(expected["code_hash"])])
        except Exception:
            return False
        return val == want
    return bool(val)


def _v_merkle_demo(p):
    return verify_inclusion(p.get("state_root"), p.get("leaf"), p.get("path", []))


def _v_eth_mpt(p):
    return verify_eth_mpt(p.get("state_root"), p.get("address"), p.get("account_proof", []), p.get("expected"))


PROOF_VERIFIERS = {"merkle-demo": _v_merkle_demo, "eth-mpt": _v_eth_mpt}


def verify_state_proof(proof_type: str, params: dict) -> bool:
    """Dispatch PLUGGABLE: il kernel verifica la prova col verificatore del tipo DICHIARATO. Tipo ignoto -> False
    (niente fiducia in un formato di prova non riconosciuto)."""
    fn = PROOF_VERIFIERS.get(proof_type)
    return bool(fn(params)) if fn else False
