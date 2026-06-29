"""substrate_core.transparency — PROTOTIPO di transparency-log + keyring (rotazione/revoca) per i certificati.

L'audit (recon 2026-06-05) ha notato che i certificati firmati non avevano: (a) un LOG append-only verificabile
(chi ha emesso cosa, a prova di rollback) e (b) rotazione/revoca delle chiavi d'emissione. Qui un PROTOTIPO
SOUND ma volutamente locale (NON una CT distribuita):

  TransparencyLog: log APPEND-ONLY di content_hash, Merkle domain-separato (riusa ads), con SIGNED TREE HEAD
    (size+root firmati Ed25519), inclusion-proof e check di CONSISTENZA (un nuovo head deve ESTENDERE il vecchio:
    root_dei_primi_old.size == old.root -> niente rollback/riscrittura della storia).
  KeyRing: piu' pubkey d'emittente con finestra di validita' [not_before, not_after] (timestamp LOGICO, es. block)
    + revoca. verify_cert accetta una busta SOLO se firmata da una chiave VALIDA-IN-FINESTRA e NON revocata.

Residuo onesto (cosa servirebbe per una CT vera): gossip/witness-cosigning fra monitor indipendenti, consistency
proof RFC6962 trasmissibili (qui il monitor TIENE le foglie e ricalcola), e un'autorita' di tempo non-locale.
"""
from __future__ import annotations

import json
from typing import List, Optional

from .ads import _build_layers, _inclusion, _recompute, _sha
from .kernel import _privkey_from_seed, _pubkey_obj, derive_pubkey, cert_from_dict, verify_sig


def _leaf(content_hash: str) -> bytes:
    return _sha(b"TLEAF\x00" + str(content_hash).encode())   # dominio-foglia del log (separato da ads)


def _sth_msg(size: int, root: str) -> bytes:
    """Byte canonici del Signed Tree Head (cio' che si firma): deterministici, indipendenti dall'ordine-chiavi."""
    return json.dumps({"size": int(size), "root": root}, sort_keys=True, separators=(",", ":")).encode("utf-8")


class TransparencyLog:
    def __init__(self, key: bytes):
        self.key = key
        self.leaves: List[str] = []     # content_hash in ordine d'inserimento (append-only)

    def append(self, content_hash: str) -> int:
        self.leaves.append(str(content_hash))
        return len(self.leaves) - 1

    def _root_at(self, size: int) -> str:
        return _build_layers([_leaf(h) for h in self.leaves[:size]])[-1][0].hex()

    def signed_head(self) -> dict:
        """Signed Tree Head: (size, root) FIRMATO. Il root committa l'INSIEME COMPLETO delle foglie fino a size."""
        size = len(self.leaves)
        root = self._root_at(size)
        sig = _privkey_from_seed(self.key).sign(_sth_msg(size, root)).hex()
        return {"size": size, "root": root, "sig": sig, "pubkey": derive_pubkey(self.key)}

    def inclusion_proof(self, i: int) -> dict:
        size = len(self.leaves)
        layers = _build_layers([_leaf(h) for h in self.leaves[:size]])
        return {"index": i, "size": size, "leaf_src": self.leaves[i],
                "path": _inclusion(layers, i), "root": self._root_at(size)}

    def consistency(self, old_head: dict) -> dict:
        """Append-only: il log attuale ESTENDE old_head sse la radice dei primi old.size foglie == old.root.
        Rileva rollback / riscrittura di una voce passata (la radice-prefisso non torna)."""
        osz = int(old_head.get("size", 0))
        extends = (osz <= len(self.leaves)) and (self._root_at(osz) == old_head.get("root"))
        return {"extends": extends, "old_size": osz, "new_size": len(self.leaves)}


def verify_signed_head(head: dict, pubkey: Optional[str] = None) -> bool:
    """Verifica la firma Ed25519 del Signed Tree Head (mai eccezione -> bool)."""
    pub = pubkey if pubkey is not None else head.get("pubkey")
    if not pub or not head.get("sig"):
        return False
    try:
        _pubkey_obj(pub).verify(bytes.fromhex(head["sig"]), _sth_msg(head["size"], head["root"]))
        return True
    except Exception:  # noqa
        return False


def verify_inclusion(proof: dict, root: Optional[str] = None) -> bool:
    """La foglia e' inclusa nell'albero di `root`? Ricompone la radice dal path (mai eccezione -> bool)."""
    r = root if root is not None else proof.get("root")
    try:
        rc, pos = _recompute(_leaf(proof["leaf_src"]), proof["path"])
        return rc.hex() == r and pos == proof["index"]
    except Exception:  # noqa
        return False


class KeyRing:
    """Rotazione + revoca delle chiavi d'emissione. Il tempo `t` e' un timestamp LOGICO (es. block number)."""
    def __init__(self):
        self.keys: List[dict] = []
        self.revoked: set = set()   # revoca DURATURA (recon 2026-06-05): una pubkey revocata resta revocata;
        #                              add() NON la resuscita (prima un re-add azzerava il flag -> bypass).

    def add(self, pubkey: str, not_before: int = 0, not_after: int = 10 ** 18) -> None:
        self.keys.append({"pubkey": pubkey, "not_before": int(not_before), "not_after": int(not_after)})

    def revoke(self, pubkey: str) -> None:
        self.revoked.add(pubkey)

    def valid_at(self, pubkey: str, t: int) -> bool:
        if pubkey in self.revoked:
            return False   # la revoca DOMINA, sempre (anche dopo un re-add)
        return any(k["pubkey"] == pubkey and k["not_before"] <= t <= k["not_after"] for k in self.keys)

    def verify_cert(self, envelope: dict, t: int) -> bool:
        """Accetta una busta SOLO se la firma e' valida E la pubkey e' valida-in-finestra e NON revocata a tempo t."""
        pub = envelope.get("pubkey")
        if not pub or not self.valid_at(pub, t):
            return False
        try:
            return verify_sig(cert_from_dict(envelope["certificate"]), envelope.get("sig"), pub)
        except Exception:  # noqa
            return False
