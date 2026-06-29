"""substrate_core.cid — indirizzamento CONTENT-ADDRESSED dei .scar / del codice (CIDv1, IPFS/IPLD-compatibile).

Prima fetta REALE dell'OVERLAY UNIVERSALE (la "Lente" a scala globale): mappa byte -> un CID stabile e
universale, cosi' un .scar o una funzione possono essere risolti per indirizzo-di-contenuto in una DHT (IPFS/
Helia) o serviti da un gateway, e ri-verificati zero-trust nel browser. TCB-PURE: SOLO hashlib + base64 (stdlib),
nessuna dipendenza esterna -> innestabile ovunque; il firewall del kernel resta intatto.

CIDv1 = <multibase 'b'> base32( <0x01 version> <0x55 raw-codec> <0x12 sha2-256> <0x20 len=32> <digest> ).
Identico a `ipfs add --cid-version=1 --raw-leaves` per un blocco raw <=256KiB: un terzo lo verifica con qualunque
implementazione IPFS standard."""
from __future__ import annotations

import base64
import hashlib

_RAW_CODEC = 0x55      # multicodec 'raw'
_SHA2_256 = 0x12       # multihash code per sha2-256
_DIGEST_LEN = 0x20     # 32 byte
_CIDV1 = 0x01          # versione CID


def scar_cid(data) -> str:
    """CIDv1 (raw, sha2-256) in multibase base32 lower-no-pad. IPFS/IPLD-compatibile. Deterministico, TCB-pure."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    mh = bytes([_SHA2_256, _DIGEST_LEN]) + hashlib.sha256(data).digest()   # multihash
    cid_bytes = bytes([_CIDV1, _RAW_CODEC]) + mh                            # CIDv1 + raw codec
    b32 = base64.b32encode(cid_bytes).decode("ascii").lower().rstrip("=")   # multibase base32 (lower, no pad)
    return "b" + b32


def decode_cid(cid: str) -> dict:
    """Decodifica un CIDv1-base32 nei suoi campi (per la verifica zero-trust lato verificatore)."""
    if not cid or cid[0] != "b":
        raise ValueError("non e' un CID multibase base32 ('b'...)")
    pad = "=" * (-len(cid[1:]) % 8)
    raw = base64.b32decode(cid[1:].upper() + pad)
    if len(raw) != 4 + 32 or raw[0] != _CIDV1 or raw[1] != _RAW_CODEC or raw[2] != _SHA2_256 or raw[3] != _DIGEST_LEN:
        raise ValueError("CID non conforme (atteso CIDv1/raw/sha2-256/32B)")
    return {"version": raw[0], "codec": raw[1], "mh_code": raw[2], "mh_len": raw[3], "digest": raw[4:].hex()}


def verify_cid(cid: str, data) -> bool:
    """Zero-trust: il CID corrisponde DAVVERO a `data`? (ricomputa lo sha2-256 e confronta col digest nel CID)."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    try:
        return decode_cid(cid)["digest"] == hashlib.sha256(data).hexdigest()
    except Exception:  # noqa
        return False
