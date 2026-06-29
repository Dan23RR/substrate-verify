"""substrate_core.firehose — INGESTIONE CONTINUA (Pilastro 2): da strumento CLI a DEMONE.

Trasforma uno STREAM di item (commit, tx pendenti, claim grezzi) in una pipeline di verifica CONTINUA: ogni item
-> Claim (via adapter pluggable) -> seam/kernel (ri-esecuzione, niente fiducia) -> certificato firmato ingerito in
un grafo WRITE-GATED; se REFUTED l'item e' un ALLARME col witness firmato (la prova portabile dell'anomalia).
Il kernel diventa il livello di validazione in tempo reale: si avventa su ogni item PRIMA che 'passi' (mined/merged).

Qui c'e' il core RIUSABILE + un adapter d'esempio. Gli adapter live (mempool Ethereum, firehose di commit GitHub)
si innestano implementando solo item->claim_dict, SENZA toccare il kernel (che resta agnostico e prover-independent).
"""
from __future__ import annotations

from typing import Callable, Optional

from .prover_seam import submit
from .cert_graph import CertGraph
from .kernel import derive_pubkey
from .export import export_bundle

_ST = {"REFUTED": "refuted", "CONFIRMED": "confirmed", "ABSTAIN": "abstain"}


def pyprop_adapter(item) -> dict:
    """Adapter d'esempio: un item = path di un file pyprop, oppure (path, params)."""
    if isinstance(item, (tuple, list)):
        path, params = item[0], (item[1] if len(item) > 1 else {})
    else:
        path, params = item, {}
    return {"domain": "pyprop", "target": str(path), "kind": "invariant", "params": dict(params)}


def watch(stream, adapter: Callable = pyprop_adapter, *, key: Optional[bytes] = None,
          graph: Optional[CertGraph] = None, on_verdict: Optional[Callable] = None,
          stop_after: Optional[int] = None) -> dict:
    """Consuma `stream` (iterabile, anche infinito). Per ogni item: adapter->claim, submit (seam+gate), ingest nel
    grafo WRITE-GATED; se REFUTED registra un ALLARME (busta firmata + witness). Ritorna {summary, graph, alarms}.
    `on_verdict(item, env, status)` e' un hook opzionale (es. push, log, webhook). Il prover resta NON-FIDATO."""
    if graph is None:
        graph = CertGraph(pubkey=(derive_pubkey(key) if key else None))   # write-gated: solo certs firmati VALIDI
    summary = {"seen": 0, "refuted": 0, "confirmed": 0, "abstain": 0}
    alarms = []
    for i, item in enumerate(stream):
        if stop_after is not None and i >= stop_after:
            break
        env = submit(adapter(item), key=key)                  # il kernel RI-ESEGUE: niente fiducia nell'item
        v = env["certificate"]["verdict"]
        st = v["status"]
        summary["seen"] += 1
        summary[_ST.get(st, "abstain")] += 1
        try:
            graph.ingest(env)                                 # busta non firmata/manomessa -> rifiutata (no poisoning)
        except Exception:  # noqa
            pass
        if st == "REFUTED":
            alarms.append({"item": _label(item), "content_hash": env["content_hash"],
                           "witness": v["witness"], "envelope": env})
        if on_verdict:
            on_verdict(item, env, st)
    return {"summary": summary, "graph": graph, "alarms": alarms}


def export_alarms(graph: CertGraph, *, key: Optional[bytes] = None, name: str = "firehose") -> dict:
    """Esporta lo stato del demone come bundle .scar firmato: la prova portabile, offline-verificabile, di TUTTO
    cio' che il demone ha verificato (verdetti + witness), autenticabile da un terzo con la sola chiave pubblica."""
    return export_bundle(graph, key=key, name=name)


def _label(item) -> str:
    import os
    p = item[0] if isinstance(item, (tuple, list)) else item
    return os.path.basename(str(p))
