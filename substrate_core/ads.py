"""substrate_core.ads — STEP 2 FASE 2: indice AUTENTICATO per query a COMPLETEZZA dimostrabile.

Il sigillo finale: non solo "cio' che e' nella scatola e' vero", ma "NULLA e' nascosto fuori". Un Merkle-tree
ORDINATO sull'asse `target` committa l'insieme COMPLETO dei fatti (la sua radice entra nell'export firmato).
Una query restituisce i match + una PROVA che non ne esistono altri:
  - ogni inclusion-proof committa anche la POSIZIONE della foglia (i bit del path = l'indice),
  - i match devono essere CONTIGUI (nessun gap dove nascondere un match),
  - i confini (left/right) devono essere NON-match adiacenti (left.key < K < right.key, posizioni adiacenti).
Se un 6° risultato fosse nascosto, dovrebbe stare tra due foglie provate adiacenti -> la prova si ROMPE.
Tutto verificabile OFFLINE contro la radice firmata, senza scansionare il DAG ne' fidarsi del motore locale.
(Single-axis `target` per Fase 2; multi-asse -> era Verkle, come da strategia.)
"""
from __future__ import annotations

import hashlib
from typing import List, Tuple


def _sha(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def _leaf(key: str, val: str) -> bytes:
    return _sha(b"L\x00" + str(key).encode() + b"\x00" + str(val).encode())


def _node(a: bytes, b: bytes) -> bytes:
    return _sha(b"N\x00" + a + b)


def _auth_root(inner_hex: str, n: int) -> str:
    """Radice AUTENTICATA = H(domain || inner_merkle_root || n). Committa la CARDINALITA' insieme alle foglie,
    cosi' `n` non e' piu' un campo libero falsificabile (chiude il truncamento di n per nascondere un match)."""
    return _sha(b"ADSROOT\x00" + bytes.fromhex(inner_hex) + b"\x00" + str(int(n)).encode()).hex()


def _build_layers(leaves: List[bytes]) -> List[List[bytes]]:
    if not leaves:
        return [[_sha(b"")]]
    layers = [list(leaves)]
    while len(layers[-1]) > 1:
        cur = layers[-1]
        layers.append([_node(cur[i], cur[i + 1] if i + 1 < len(cur) else cur[i]) for i in range(0, len(cur), 2)])
    return layers


def _inclusion(layers: List[List[bytes]], idx: int) -> List[list]:
    path = []
    for d in range(len(layers) - 1):
        cur = layers[d]
        sib = idx ^ 1
        path.append([(cur[sib] if sib < len(cur) else cur[idx]).hex(), idx & 1])
        idx >>= 1
    return path


def _recompute(leaf: bytes, path: List[list]) -> Tuple[bytes, int]:
    cur, pos = leaf, 0
    for d, (sib_hex, bit) in enumerate(path):
        sib = bytes.fromhex(sib_hex)
        cur = _node(sib, cur) if bit else _node(cur, sib)
        pos |= (bit << d)
    return cur, pos


def build_index(entries, axis: str = "target") -> dict:
    """entries: iterable di (key, value). Costruisce un Merkle-tree ORDINATO; la radice committa l'INSIEME COMPLETO."""
    se = sorted(((str(k), str(v)) for k, v in entries))
    layers = _build_layers([_leaf(k, v) for k, v in se])
    inner = layers[-1][0].hex()      # radice Merkle delle sole foglie (le inclusion-proof ricompongono a QUESTA)
    n = len(se)
    return {"axis": axis, "inner": inner, "root": _auth_root(inner, n), "n": n, "_entries": se, "_layers": layers}


def _entry_proof(index: dict, i: int) -> dict:
    k, v = index["_entries"][i]
    return {"pos": i, "key": k, "val": v, "proof": _inclusion(index["_layers"], i)}


def query(index: dict, key) -> dict:
    """Query per `key` sull'asse: ritorna i match + i confini, ognuno con inclusion-proof (la prova di completezza)."""
    key = str(key)
    se = index["_entries"]
    n = len(se)
    pos = [i for i, (k, _) in enumerate(se) if k == key]
    res = {"key": key, "root": index["root"], "inner": index["inner"], "n": n, "axis": index["axis"],
           "matches": [], "left": None, "right": None}
    if pos:
        p, q = pos[0], pos[-1]
        res["matches"] = [_entry_proof(index, i) for i in pos]
        if p > 0:
            res["left"] = _entry_proof(index, p - 1)
        if q < n - 1:
            res["right"] = _entry_proof(index, q + 1)
    else:
        left = max((i for i, (k, _) in enumerate(se) if k < key), default=None)
        right = min((i for i, (k, _) in enumerate(se) if k > key), default=None)
        if left is not None:
            res["left"] = _entry_proof(index, left)
        if right is not None:
            res["right"] = _entry_proof(index, right)
    return res


def verify_query(result: dict, expected_root: str = None) -> dict:
    """Verifica OFFLINE. complete=True SOLO se nulla e' nascosto (contiguita' + confini non-match + cardinalita').

    ANCORAGGIO (recon 2026-06-05): verify_query controlla la CONSISTENZA INTERNA contro result['root']. E' SOUND
    contro un avversario solo se il chiamante PINNA la radice autentica (firmata): passa `expected_root`, altrimenti
    un avversario puo' fornire un SOTTOINSIEME forgiato con la SUA radice auto-consistente (che nasconde un match)."""
    if expected_root is not None and result.get("root") != expected_root:
        return {"complete": False, "reason": "root NON combacia con la radice PINNATA (sottoinsieme forgiato?)", "matches": []}
    n, key = result["n"], result["key"]
    inner_hex = result.get("inner")
    # BINDING DI CARDINALITA' (recon 2026-06-05): la radice AUTENTICATA committa (inner_root || n). Un avversario
    # che TRUNCA `n` per nascondere un match "oltre la fine" (spacciando una foglia interna per l'ultima) rompe
    # questa uguaglianza -> completezza FALSA. Chiude il buco "n non autenticato".
    if not inner_hex or result.get("root") != _auth_root(inner_hex, n):
        return {"complete": False, "reason": "cardinalita' n NON autenticata dalla radice (truncamento?)", "matches": []}
    inner = bytes.fromhex(inner_hex)

    def chk(e):
        rc, pos = _recompute(_leaf(e["key"], e["val"]), e["proof"])
        return rc == inner and pos == e["pos"]

    def fail(why):
        return {"complete": False, "reason": why, "matches": []}

    matches = result["matches"]
    if not all(chk(m) for m in matches):
        return fail("inclusion-proof di un match invalida")
    if result["left"] and not chk(result["left"]):
        return fail("left-boundary invalida")
    if result["right"] and not chk(result["right"]):
        return fail("right-boundary invalida")

    if matches:
        ps = [m["pos"] for m in matches]
        if ps != list(range(ps[0], ps[-1] + 1)):
            return fail("match NON contigui (gap = possibile match nascosto)")
        if any(m["key"] != key for m in matches):
            return fail("match con chiave sbagliata")
        if result["left"]:
            if not (result["left"]["key"] < key and result["left"]["pos"] == ps[0] - 1):
                return fail("left-boundary non adiacente o non-minore -> possibile match nascosto a sinistra")
        elif ps[0] != 0:
            return fail("manca il left-boundary ma i match non iniziano a 0")
        if result["right"]:
            if not (result["right"]["key"] > key and result["right"]["pos"] == ps[-1] + 1):
                return fail("right-boundary non adiacente o non-maggiore -> possibile match nascosto a destra")
        elif ps[-1] != n - 1:
            return fail("manca il right-boundary ma i match non finiscono a n-1")
        return {"complete": True, "matches": [(m["key"], m["val"]) for m in matches], "n_matches": len(matches)}

    # non-membership: prova di ASSENZA (vicini adiacenti che racchiudono key)
    l, r = result["left"], result["right"]
    if l and r:
        if l["key"] < key < r["key"] and r["pos"] == l["pos"] + 1:
            return {"complete": True, "absent": True, "matches": []}
        return fail("vicini non adiacenti -> assenza non provata")
    if r and not l:
        if key < r["key"] and r["pos"] == 0:
            return {"complete": True, "absent": True, "matches": []}
    if l and not r:
        if l["key"] < key and l["pos"] == n - 1:
            return {"complete": True, "absent": True, "matches": []}
    if not l and not r and n == 0:
        return {"complete": True, "absent": True, "matches": []}
    return fail("assenza non provata")
