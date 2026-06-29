#!/usr/bin/env python
"""verify_all.py — UN comando per riprodurre il green-board di substrate_core (contestabile/ri-eseguibile).

Verifica il KERNEL (claim->exec-gate->certificato 3-vie firmato/componibile) su domini eterogenei:
  - pyprop  (Python property fuzz)   self-contained, sempre
  - erc4626 (forge exec-gate)        se verivault+forge presenti
+ firma/tamper, content_hash deterministico, composizione sound (incl. CROSS-DOMINIO), organismo, ABSTAIN onesto.
Ritorna exit!=0 se QUALSIASI assert fallisce.
"""
from __future__ import annotations
import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import substrate_core as sc
from substrate_core import Claim, verify, compose_bundle
from substrate_core.organism import sweep
from substrate_core.kernel import Certificate, Verdict, Status, verify_sig, weakest, EMPIRICAL, BOUNDED, PROVEN

EX = os.path.join(HERE, "examples")
KEY = b"verify-all-key"
results = []
def check(name, cond): results.append((name, bool(cond)))
import importlib.util as _ilu, shutil as _shutil
def _have(mod): return _ilu.find_spec(mod) is not None   # optional dep present? -> honest SKIP when absent

# 1) import + registro
check("import substrate_core", True)
check("dominio pyprop registrato", "pyprop" in sc.REGISTRY)
check("lattice STRETTAMENTE ordinato (empirical<bounded<proven)", weakest([BOUNDED, PROVEN, EMPIRICAL]) == EMPIRICAL)

# 2) pyprop CONFIRMED (eseguito)
e1 = verify(Claim("pyprop", os.path.join(EX, "ex_abs.py"), "invariant", {"trials": 500, "seed": 0}), key=KEY)
check("pyprop ex_abs -> CONFIRMED", e1["certificate"]["verdict"]["status"] == "CONFIRMED")
check("pyprop ex_abs eseguito", e1["certificate"]["verdict"]["executed"])
check("pyprop CONFIRMED -> assurance=empirical (NON prova)", e1["certificate"]["verdict"]["assurance"] == "empirical")
check("pyprop empirical porta un rischio-residuo numerico", isinstance(e1["certificate"]["verdict"].get("residual_risk"), (int, float)))

# 3) pyprop REFUTED + witness eseguito
e2 = verify(Claim("pyprop", os.path.join(EX, "ex_buggy_sort.py"), "invariant", {"trials": 500, "seed": 0}), key=KEY)
check("pyprop ex_buggy_sort -> REFUTED", e2["certificate"]["verdict"]["status"] == "REFUTED")
check("REFUTED porta un witness", bool(e2["certificate"]["verdict"]["witness"]))
check("pyprop REFUTED -> assurance=proven (controesempio sound)", e2["certificate"]["verdict"]["assurance"] == "proven")

# META-VERIFICA HARNESS (critica #2): una prop VACUA non deve dare CONFIRMED ma ABSTAIN(harness-non-adeguato)
e_vac = verify(Claim("pyprop", os.path.join(EX, "ex_vacuous.py"), "invariant", {"trials": 300, "seed": 0}), key=KEY)
check("harness vacuo -> ABSTAIN (declassato, NON CONFIRMED)", e_vac["certificate"]["verdict"]["status"] == "ABSTAIN")
check("harness adeguato (ex_abs) resta CONFIRMED", e1["certificate"]["verdict"]["status"] == "CONFIRMED")

# GRAFO DI CERTIFICATI proof-carrying (memoria, punto sicuro): provenance-gating + integrita' crittografica
from substrate_core import CertGraph, ProvenanceError
_g = CertGraph()
_g.ingest(e1); _g.ingest(e2)
check("cert-graph: ogni nodo ingerito porta una provenance", bool(_g.nodes) and all(n["provenance"] for n in _g.nodes.values()))
check("cert-graph: integrita' INTATTA (hash+firma di ogni cert)", _g.verify_integrity(key=KEY)["intact"])
_gated = False
try:
    _g._node("x", "entity", provenance="")   # scrittura senza certificato
except ProvenanceError:
    _gated = True
check("cert-graph: GATING rifiuta scrittura senza certificato", _gated)

# FIREWALL DEL DETERMINISMO (prover-independence): l'agente e' un CLIENT NON-FIDATO che non puo' coniare verita'
import inspect as _insp, re as _re, substrate_core.kernel as _kmod
from substrate_core.prover_seam import submit as _submit
_imps = _re.findall(r'^\s*(?:import|from)\s+([\w\.]+)', _insp.getsource(_kmod), _re.M)
_FORBIDDEN = ("openai", "anthropic", "smolagents", "langchain", "langgraph", "requests", "urllib",
              "httpx", "socket", "torch", "transformers", "subprocess", "pickle")
check("firewall: kernel (TCB) NON importa LLM/rete/agente/subprocess",
      not any(any(f in imp for f in _FORBIDDEN) for imp in _imps))
_hv = _submit({"domain": "pyprop", "target": os.path.join(EX, "ex_vacuous.py"),
               "params": {"trials": 300, "seed": 0, "assurance": "proven", "status": "CONFIRMED"}}, key=KEY)
check("firewall: prover mente 'proven' su harness vacuo -> ABSTAIN", _hv["certificate"]["verdict"]["status"] == "ABSTAIN")
_ho = _submit({"domain": "pyprop", "target": os.path.join(EX, "ex_abs.py"),
               "params": {"trials": 200, "seed": 0, "assurance": "proven"}}, key=KEY)
check("firewall: assurance asserito dal prover STRIPPATO (resta empirical, non proven)",
      _ho["certificate"]["verdict"]["assurance"] == "empirical")
check("firewall: dominio allucinato -> ABSTAIN (kernel totale, no crash)",
      _submit({"domain": "ghost_domain", "target": "x"}, key=KEY)["certificate"]["verdict"]["status"] == "ABSTAIN")

# RESOURCE-NORMALIZATION (STEP 0, recon-fix): il prover non puo' fabbricare un verdetto coi PARAMETRI d'esecuzione.
# Buco VERIFICATO e ora CHIUSO: trials=0 dava un CONFIRMED falso; wall_s~0 sopprimeva una REFUTED reale.
_bsort = os.path.join(EX, "ex_buggy_sort.py")
_g0 = _submit({"domain": "pyprop", "target": _bsort, "kind": "invariant", "params": {"trials": 0}}, key=KEY)
check("STEP0: prover chiede trials=0 su sort buggato -> REFUTED (NIENTE CONFIRMED falso: floor del kernel)",
      _g0["certificate"]["verdict"]["status"] == "REFUTED")
check("STEP0: 'trials' finisce in stripped_budget (audit: il prover non controlla il budget)",
      "trials" in _g0["prover"].get("stripped_budget", []))
_g0b = verify(Claim("pyprop", _bsort, "invariant", {"trials": 0}), key=KEY)
check("STEP0: difesa-in-profondita' — anche verify() diretto con trials=0 -> REFUTED (floor nel gate, non solo seam)",
      _g0b["certificate"]["verdict"]["status"] == "REFUTED")
_g0c = verify(Claim("pyprop", _bsort, "invariant", {"wall_s": 0.0005}), key=KEY)
check("STEP0: wall_s~0 per SOPPRIMERE la refutazione -> REFUTED comunque (floor wall_s, anti-soppressione)",
      _g0c["certificate"]["verdict"]["status"] == "REFUTED")

# CONTRACT-GATE (Pilastro 1): teoria-dei-tipi al confine. Input fuori-contratto scartati SENZA spendere il budget.
from substrate_core.contracts import check_contract as _cc
check("contract: list[int] accetta [1,2,3]", _cc([1, 2, 3], "list[int]"))
check("contract: list[int] RIFIUTA [[1],[2]] (e' list[list[int]])", not _cc([[1], [2]], "list[int]"))
check("contract: list[int] RIFIUTA [1,'a'] (elemento str)", not _cc([1, "a"], "list[int]"))
check("contract: unione int|none", _cc(None, "int|none") and _cc(5, "int|none") and not _cc("x", "int|none"))
check("contract: bool NON e' int (nessuna confusione di tipo)", _cc(True, "bool") and not _cc(True, "int"))
_garb = os.path.join(EX, "ex_contract_garbage.py")
_cgv = verify(Claim("pyprop", _garb, "invariant", {"contract": "list[int]"}), key=KEY)
check("CONTRACT-GATE: gen fuori-contratto (list[list[int]] vs list[int]) -> ABSTAIN(contract), niente fuzz sprecato",
      _cgv["certificate"]["verdict"]["status"] == "ABSTAIN"
      and (_cgv["certificate"]["verdict"].get("coverage", {}) or {}).get("contract_violation"))
_cgok = verify(Claim("pyprop", _garb, "invariant", {"contract": "list[list[int]]"}), key=KEY)
check("CONTRACT-GATE: stesso gen col contratto GIUSTO (list[list[int]]) -> NON contract-violation (input validi)",
      not (_cgok["certificate"]["verdict"].get("coverage", {}) or {}).get("contract_violation"))
_cgno = verify(Claim("pyprop", _garb, "invariant", {}), key=KEY)
check("CONTRACT-GATE: senza contratto dichiarato, comportamento INVARIATO (zero validazione di tipo)",
      not (_cgno["certificate"]["verdict"].get("coverage", {}) or {}).get("contract_violation"))

# PASSAGGIO DI TESTIMONE (proof-carrying dataflow) + INVALIDAZIONE A CASCATA
from substrate_core.pipeline import pipe as _pipe
_src = verify(Claim("pyprop", os.path.join(EX, "real_cream_vault.py"), "attacker_cannot_profit",
                    {"trials": 2000, "seed": 0}), key=KEY)
check("witness-pass: sorgente cream -> REFUTED (il witness porta il param d'attacco)",
      _src["certificate"]["verdict"]["status"] == "REFUTED")
_nxt = _pipe(_src, {"domain": "replay", "target": "cream-attack", "kind": "replay_exploit"}, key=KEY)
_nv = _nxt["certificate"]["verdict"]
check("witness-pass: replay coi param PASSATI -> CONFIRMED/proven (cross-dominio)",
      _nv["status"] == "CONFIRMED" and _nv["assurance"] == "proven")
check("witness-pass: link CRYPTOGRAFICO input_from == content_hash sorgente",
      _nxt["certificate"]["claim"]["params"]["input_from"] == _src["content_hash"])
_cg2 = CertGraph(); _cg2.ingest(_src); _cg2.ingest(_nxt)
check("cascade: invalidare il sorgente invalida il cert DIPENDENTE",
      _nxt["content_hash"] in _cg2.invalidate(_src["content_hash"])["invalidated"])

# BINDING del witness-passing (R3): il legame e' un check del kernel, non una pretesa del prover
from substrate_core.pipeline import binding_verified as _bind
import copy as _copy
check("binding: pipe onesto -> legame VERIFICATO (input_from==hash & witness combaciano)", _bind(_src, _nxt))
_fab = _submit({"domain": "replay", "target": "x", "kind": "replay_exploit",
                "params": {"input_witness": {"input": "(999999999, 1)"}, "input_from": "deadbeef"}}, key=KEY)
check("binding: prover FABBRICA un witness cross-dominio -> ABSTAIN (input_from/witness strippati dal seam)",
      _fab["certificate"]["verdict"]["status"] == "ABSTAIN")
_tamper = _copy.deepcopy(_nxt)
_tamper["certificate"]["claim"]["params"]["input_witness"] = {"input": "(1, 1)"}
check("binding: legame MANOMESSO rilevato (witness non combacia col sorgente)", not _bind(_src, _tamper))

# ONTOLOGIA proof-carrying (R1, chiude la breccia): il TIPO d'entita' = cert su PROBE eseguito, mai etichetta.
# PROVEN co-proprieta' (recon 2026-06-05) RICHIEDE una inclusion-proof legata a uno state_root PINNATO (anti-conio):
# cospend_inputs ASSERITI da soli -> ABSTAIN(needs-proof). Qui esibiamo una prova merkle-demo valida -> PROVEN.
from substrate_core.statelight import build_proof as _bp_cospend
_cospend_leaf = {"cospend_tx": "0xt", "inputs": ["0xA", "0xB"]}
_cospend_root, _cospend_path = _bp_cospend(_cospend_leaf, ["aa11", "bb22"])
_pc = verify(Claim("entity_probe", "0xA-0xB", "entity_type:co_owned",
                   {"probe": "crypto", "a": "0xA", "b": "0xB", "cospend_inputs": ["0xA", "0xB"], "tx": "0xt",
                    "context": {"chain_id": 1, "block": 18500000, "state_root": _cospend_root},
                    "state_proof": {"proof_type": "merkle-demo", "leaf": _cospend_leaf, "path": _cospend_path}}), key=KEY)
check("entity_probe crypto (co-spend + inclusion-proof) -> PROVEN", _pc["certificate"]["verdict"]["assurance"] == "proven")
_pc_noproof = verify(Claim("entity_probe", "0xA-0xB", "entity_type:co_owned",
                           {"probe": "crypto", "a": "0xA", "b": "0xB", "cospend_inputs": ["0xA", "0xB"], "tx": "0xt"}), key=KEY)
check("entity_probe crypto SENZA inclusion-proof -> ABSTAIN(needs-proof) (anti-conio del PROVEN)",
      _pc_noproof["certificate"]["verdict"]["status"] == "ABSTAIN")
_po = verify(Claim("entity_probe", "0xVAULT", "entity_type:erc4626",
                   {"probe": "onchain", "interface": "erc4626",
                    "source": "function deposit() function redeem() function totalAssets() function convertToShares()"}), key=KEY)
check("entity_probe onchain (interfaccia) -> PROVEN-SPEC", _po["certificate"]["verdict"]["assurance"] == "proven-spec")
_feat = {"unique_counterparties": 5000, "in_out_ratio": 1.0, "deposit_withdraw_symmetry": 0.9}
_pb = verify(Claim("entity_probe", "0xEXCH", "entity_type:exchange",
                   {"probe": "behavioral", "features": _feat, "data_window": "blocks 18000000-18100000"}), key=KEY)
check("entity_probe behavioral (exchange, finestra PINNATA) -> EMPIRICAL", _pb["certificate"]["verdict"]["assurance"] == "empirical")
check("entity_probe behavioral porta un rischio-residuo", isinstance(_pb["certificate"]["verdict"].get("residual_risk"), (int, float)))
_pbno = verify(Claim("entity_probe", "0xEXCH", "entity_type:exchange", {"probe": "behavioral", "features": _feat}), key=KEY)
check("entity_probe behavioral SENZA finestra pinnata -> ABSTAIN (ermeticita')", _pbno["certificate"]["verdict"]["status"] == "ABSTAIN")
check("entity_probe: prover che ASSERISCE assurance -> strippato (il tier viene dal probe, non dal prover)",
      _submit({"domain": "entity_probe", "target": "0xX", "kind": "entity_type:exchange",
               "params": {"probe": "behavioral", "features": _feat, "data_window": "b1-b2", "assurance": "proven"}}, key=KEY)["certificate"]["verdict"]["assurance"] == "empirical")
_cg3 = CertGraph(); _cg3.ingest(_po)
check("cert-graph: un entity_probe TIPA il nodo (entity_type backed da un probe)", bool(_cg3.typed_entities()))

# LIBRERIA DI ALESSANDRIA: ingestione GATED — solo dato con VERITA' ESEGUIBILE entra nel corpus (zero allucinazione)
from substrate_core.harvest import gated_ingest
_cands = [{"domain": "pyprop", "target": os.path.join(EX, "ex_abs.py"), "params": {"trials": 300, "seed": 0}},
          {"domain": "pyprop", "target": os.path.join(EX, "ex_buggy_sort.py"), "params": {"trials": 300, "seed": 0}},
          {"domain": "pyprop", "target": os.path.join(EX, "ex_vacuous.py"), "params": {"trials": 300, "seed": 0}}]
_corpus, _rej = gated_ingest(_cands, key=KEY)
check("harvest: il corpus tiene solo verita' eseguibile (ex_abs CONFIRMED + ex_buggy_sort REFUTED)", len(_corpus) == 2)
check("harvest: l'harness VACUO e' RIFIUTATO dal corpus (zero allucinazione nei dati)",
      len(_rej) == 1 and "ex_vacuous" in _rej[0]["target"])

# GAS METER (DoS / terminazione): un prover CAOTICO non crasha il kernel -> ABSTAIN(resource), entro il budget
_loop = verify(Claim("pyprop", os.path.join(EX, "ex_infinite_loop.py"), "invariant",
                     {"trials": 100, "seed": 0, "wall_s": 3}), key=KEY)
_lv = _loop["certificate"]["verdict"]
check("gas-meter: subject con while-True -> ABSTAIN(resource), kernel NON crashato",
      _lv["status"] == "ABSTAIN" and "risorse" in (_lv["reason"] or "").lower())
_bomb = verify(Claim("pyprop", os.path.join(EX, "ex_memory_bomb.py"), "invariant",
                     {"trials": 5, "seed": 0, "wall_s": 8, "mem_mb": 256}), key=KEY)
check("gas-meter: subject memory-bomb -> ABSTAIN(resource/eccezione), kernel NON crashato",
      _bomb["certificate"]["verdict"]["status"] == "ABSTAIN")

# VERITA' A 4 DIMENSIONI (TOCTOU) + KERNEL LIGHT-CLIENT (oracolo): scope nel hash, inclusion-proof, composizione, decadimento
from substrate_core.temporal import scope as _scope, is_live as _islive
from substrate_core.statelight import build_proof as _bp, ProofStore as _PS
_leafV = {"what": "ERC4626-bytecode", "addr": "0xVault"}
_rootN, _pathN = _bp(_leafV, ["aa11", "bb22", "cc33"])    # stato @ block N
_rootM, _pathM = _bp(_leafV, ["aa11", "bb22", "dd44"])    # stato @ block M (proxy upgrade -> root diverso)
_srcV = "function deposit() function redeem() function totalAssets() function convertToShares()"
def _eprobe(ctx, leaf, path):
    return verify(Claim("entity_probe", "0xVault", "entity_type:erc4626",
                        {"probe": "onchain", "interface": "erc4626", "source": _srcV, "context": ctx,
                         "state_proof": {"leaf": leaf, "path": path}}), key=KEY)
_ctxN = {"chain_id": 1, "block": 18500000, "state_root": _rootN}
_ctxM = {"chain_id": 1, "block": 18600000, "state_root": _rootM}
_vN = _eprobe(_ctxN, _leafV, _pathN)
_vM = _eprobe(_ctxM, _leafV, _pathM)
check("light-client: cert state-bound con INCLUSION-PROOF valida -> CONFIRMED", _vN["certificate"]["verdict"]["status"] == "CONFIRMED")
_noproof = verify(Claim("entity_probe", "0xVault", "entity_type:erc4626",
                        {"probe": "onchain", "interface": "erc4626", "source": _srcV, "context": _ctxN}), key=KEY)
check("light-client: cert state-bound SENZA inclusion-proof -> ABSTAIN(invalid-data-proof) (no fede nel nodo RPC)",
      _noproof["certificate"]["verdict"]["status"] == "ABSTAIN" and "data-proof" in _noproof["certificate"]["verdict"]["reason"])
_bad = _eprobe(_ctxN, _leafV, _pathM)   # path del blocco SBAGLIATO -> non combacia con rootN
check("light-client: inclusion-proof MANOMESSA -> ABSTAIN(invalid-data-proof)",
      _bad["certificate"]["verdict"]["status"] == "ABSTAIN" and "data-proof" in _bad["certificate"]["verdict"]["reason"])
check("temporal: lo scope (block/state_root) e' nel content_hash (stati diversi -> hash diversi)", _vN["content_hash"] != _vM["content_hash"])
check("temporal: scope() legge l'istante esatto dal cert firmato", _scope(_vN)["block"] == 18500000)
_csys = compose_bundle([_vN, _vM], "and", key=KEY)
check("temporal: compose di STATI INCOMPATIBILI -> ABSTAIN(temporal-mismatch)",
      _csys["certificate"]["verdict"]["status"] == "ABSTAIN" and "temporal" in _csys["certificate"]["verdict"]["reason"])
_csame = compose_bundle([_vN, e1], "and", key=KEY)   # state-bound + ETERNO (pyprop) -> eredita lo scope state-bound
check("temporal: compose state-bound + ETERNO -> CONFIRMED ed eredita lo scope",
      _csame["certificate"]["verdict"]["status"] == "CONFIRMED" and (_scope(_csame) or {}).get("state_root") == _rootN)
_cgT = CertGraph(); _cgT.ingest(_vN)
check("temporal: state-change sul target -> cert CONFIRMED decade a STALE (non REFUTED)",
      _vN["content_hash"] in _cgT.decay(changed_targets=["0xVault"])["stale"])
check("temporal: liveness — cert @rootN non e' live se HEAD=rootM, live se HEAD=rootN",
      (not _islive(_vN, _rootM)) and _islive(_vN, _rootN))
_ps = _PS()
_c1 = _ps.put_path(_pathN)
_, _p2 = _bp({"what": "X", "addr": "0xOther"}, ["aa11", "bb22", "ff66"])   # condivide aa11,bb22 col path di _vN
_c2 = _ps.put_path(_p2)
check("dedup: ProofStore salva i nodi-prova CONDIVISI una volta (crescita SUB-LINEARE)",
      _ps.stats()["unique_nodes"] < len(_c1) + len(_c2))

# KERNEL LIGHT-CLIENT REALE (eth-mpt): verifica OFFLINE un eth_getProof MAINNET REALE (py-trie battle-tested)
import json as _json
from substrate_core.statelight import verify_state_proof as _vsp
_fixp = os.path.join(EX, "eth_proof_fixture.json")
try:
    import trie as _trie_mod  # noqa
    _HAS_TRIE = True
except Exception:
    _HAS_TRIE = False
if os.path.exists(_fixp) and _HAS_TRIE:
    _fix = _json.load(open(_fixp, encoding="utf-8"))
    _mptp = {"state_root": _fix["state_root"], "address": _fix["address"], "account_proof": _fix["account_proof"],
             "expected": {"nonce": _fix["nonce"], "balance": _fix["balance"],
                          "storage_hash": _fix["storage_hash"], "code_hash": _fix["code_hash"]}}
    check("eth-mpt: verifica OFFLINE di un eth_getProof MAINNET REALE -> valida (crittografia vera)", _vsp("eth-mpt", _mptp))
    _badmpt = dict(_mptp); _badmpt["state_root"] = "0x" + "00" * 32
    check("eth-mpt: state_root MANOMESSO -> la prova reale e' RIFIUTATA", not _vsp("eth-mpt", _badmpt))
    _vReal = verify(Claim("entity_probe", _fix["address"], "entity_type:erc20",
                          {"probe": "onchain", "interface": "erc20",
                           "source": "function transfer() function balanceOf() function totalSupply()",
                           "context": {"chain_id": 1, "block": _fix["block"], "state_root": _fix["state_root"]},
                           "state_proof": {"proof_type": "eth-mpt", "address": _fix["address"],
                                           "account_proof": _fix["account_proof"],
                                           "expected": {"nonce": _fix["nonce"], "balance": _fix["balance"],
                                                        "storage_hash": _fix["storage_hash"], "code_hash": _fix["code_hash"]}}}), key=KEY)
    check("eth-mpt: entity_probe con inclusion-proof MAINNET REALE supera il light-client",
          "invalid-data-proof" not in (_vReal["certificate"]["verdict"]["reason"] or ""))
else:
    results.append(("eth-mpt: py-trie/fixture mainnet assenti -> SKIP", None))

# STEP 2 — EXPORT R6 (Fase 1): la verita' come OGGETTO TRASPORTABILE, verificabile OFFLINE da un verificatore FRESCO
from substrate_core.export import export_bundle, save_bundle, load_bundle, verify_bundle
_geg = CertGraph(); _geg.ingest(_po)
if _HAS_TRIE and os.path.exists(_fixp):
    _geg.ingest(_vReal)   # un cert on-chain con la prova eth-mpt mainnet EMBEDDED
_bp = os.path.join(EX, "_test_bundle.scar")
save_bundle(export_bundle(_geg, key=KEY, name="test-investigation"), _bp)
_rep = verify_bundle(load_bundle(_bp), key=KEY)   # caricato FRESCO -> offline
check("export: bundle .scar caricato FRESCO -> INTATTO (hash+firma+radice Merkle, zero rete/DB)", _rep["intact"])
_tb = load_bundle(_bp); _k0 = next(iter(_tb["certs"]))
_tb["certs"][_k0]["certificate"]["verdict"]["status"] = "REFUTED"   # manomissione
check("export: cert MANOMESSO nel bundle -> il verificatore lo RILEVA (content_hash non torna)",
      not verify_bundle(_tb, key=KEY)["intact"])
if _HAS_TRIE and os.path.exists(_fixp):
    check("export: prova eth-mpt EMBEDDED ri-eseguita OFFLINE nel bundle (zero RPC)",
          _rep["checks"]["embedded_proofs"]["verified"] >= 1)
check("export: index_root ADS coerente coi certs (commette l'insieme COMPLETO)", _rep["checks"]["index_root_ok"])

# STEP 2 FASE 2 — ADS: query a COMPLETEZZA dimostrabile ("5 risultati, non 6", verificabile offline)
from substrate_core.ads import build_index as _bi, query as _aq, verify_query as _vq2
_ents = [("0xA", "c1"), ("0xB", "c2"), ("0xB", "c3"), ("0xC", "c4")]
_idx = _bi(_ents)
_q = _aq(_idx, "0xB")
_vqr = _vq2(_q)
check("ADS: query restituisce i match + prova di COMPLETEZZA (2 di 2, nulla nascosto)",
      _vqr["complete"] and _vqr.get("n_matches") == 2)
_hidden = dict(_q); _hidden["matches"] = [_q["matches"][0]]   # un avversario NASCONDE un match
check("ADS: nascondere un match -> RILEVATO (contiguita'/confine rotti, completezza FALSA)",
      not _vq2(_hidden)["complete"])
_vabs = _vq2(_aq(_idx, "0xB5"))   # chiave ASSENTE -> prova di assenza
check("ADS: query su chiave ASSENTE -> prova di ASSENZA (vicini adiacenti)", _vabs["complete"] and _vabs.get("absent"))

# L2 — LOOP EPISTEMICO: l'esploratore CAOTICO sopra il kernel inesorabile (il prover non sa che il kernel esiste)
from substrate_core.agent import epistemic_loop, ScriptedProver, ChaoticProver, arena, BlueProver, RedProver
import tempfile as _tf
_wd = _tf.mkdtemp(prefix="l2_")
_loop = epistemic_loop(ScriptedProver(_wd), "OZVault.sol", key=KEY, max_iters=4)
check("L2: il prover impara dal WITNESS REFUTED e conia un CONFIRMED (refutation-guided)",
      _loop["won"] and _loop["iters"] >= 2)
_chaos = epistemic_loop(ChaoticProver(_wd, fast=True), "x", key=KEY, max_iters=4)
check("L2: prover CAOTICO -> MAI un CONFIRMED-proven falso (l'infra regge l'irrazionalita')",
      not _chaos["won"] and all(not (t["status"] == "CONFIRMED" and t["assurance"] == "proven") for t in _chaos["trail"]))
check("L2 arena: Red trova il bug in un Blue BUGGATO -> REFUTED (Red vince)",
      arena(BlueProver(_wd, buggy=True), RedProver(_wd), _wd, key=KEY)[0]["status"] == "REFUTED")
check("L2 arena: Blue SOUND + harness adeguato -> CONFIRMED (Blue vince)",
      arena(BlueProver(_wd, buggy=False), RedProver(_wd), _wd, key=KEY)[0]["status"] == "CONFIRMED")

# STEP 1 — KILL-TEST dell'AMNESIA: due bug INDIPENDENTI. Col trail COMPLETO il prover li ripara entrambi; col
# solo ultimo witness OSCILLA e non converge. Questo test FALLIREBBE senza l'iniezione di traiettoria del loop.
from substrate_core.agent import TwoBugProver, FrozenProver, FakeLLMProver, _parse_claim as _pcl
_full = epistemic_loop(TwoBugProver(_wd, memory="full"), _bsort, key=KEY, max_iters=8)
_lastm = epistemic_loop(TwoBugProver(_wd, memory="last"), _bsort, key=KEY, max_iters=8)
check("STEP1: prover con TRAIETTORIA COMPLETA ripara 2 bug indipendenti -> CONFIRMED (amnesia CURATA)",
      _full["won"])
check("STEP1 kill-test: prover con SOLO l'ultimo witness OSCILLA, 8/8 REFUTED, mai CONFIRMED (amnesia)",
      (not _lastm["won"]) and _lastm["iters"] == 8 and all(t["status"] == "REFUTED" for t in _lastm["trail"]))

# STEP 6 — ANTI-LOOP: stesso controesempio deterministico ripetuto -> marcato 'stalled' (degeneration-of-thought).
_frz = epistemic_loop(FrozenProver(_wd), "x", key=KEY, max_iters=4)
check("STEP6 anti-loop: stesso witness ripetuto -> 'stalled' rilevato (e niente CONFIRMED)",
      (not _frz["won"]) and any(t.get("stalled") for t in _frz["trail"]))

# STEP 2 — PARSER DIFENSIVO: output LLM patologici NON crashano il loop PRIMA del seam (totalita' preservata).
check("STEP2 parser: ```json fenced -> dict valido", _pcl('```json\n{"domain":"pyprop"}\n```').get("domain") == "pyprop")
check("STEP2 parser: prosa pura -> sentinella __unparseable__ (nessuna eccezione)",
      _pcl("non lo so, mi dispiace").get("domain") == "__unparseable__")
check("STEP2 parser: sentinella non-parsabile -> ABSTAIN dal kernel (totalita')",
      _submit(_pcl("blah blah"), key=KEY)["certificate"]["verdict"]["status"] == "ABSTAIN")
_fk = epistemic_loop(FakeLLMProver(_bsort), _bsort, key=KEY, max_iters=4)
check("STEP2: 4 output LLM patologici (prosa/markdown/troncato/dominio-finto) -> loop SOPRAVVIVE senza crash",
      len(_fk["trail"]) == 4 and all(t["status"] in ("REFUTED", "CONFIRMED", "ABSTAIN") for t in _fk["trail"]))
check("STEP2: il kernel resta VIVO dopo gli output patologici",
      verify(Claim("pyprop", os.path.join(EX, "ex_abs.py"), "invariant", {}), key=KEY)["certificate"]["verdict"]["status"] == "CONFIRMED")

# CHEATBENCH (ramo audace, MISURATO non assunto): quanti canali di cheating restano? Ground-truth verificata.
from substrate_core.cheatbench import run_cheatbench as _runcb, row as _cbrow
_cb_off = _runcb(edge_probe=False)   # baseline senza co-fuzzer kernel
_cb_on = _runcb(edge_probe=True)     # con co-fuzzer kernel
check("cheatbench: ground-truth — ogni canale ha un subject DIMOSTRABILMENTE buggato",
      all(r["ground_truth_buggy"] for r in _cb_on["rows"]))
check("cheatbench: asserzione/budget/vacuita' -> CHIUSI (zero CONFIRMED falso su questi 4 canali)",
      all(not _cbrow(_cb_on, c)["cheated"] for c in ("assert_truth", "trials_zero", "wall_tiny", "vacuous_prop")))
check("cheatbench: 'evasione-regione' (gen evita i negativi) -> CHIUSO dal co-fuzzer kernel (era APERTO senza)",
      _cbrow(_cb_off, "gen_evasion_region")["cheated"] and not _cbrow(_cb_on, "gen_evasion_region")["cheated"])
check("cheatbench (ONESTO): 'evasione-punto-singolo' resta APERTO -> cheating_rate MISURATO = 1/6, NON 0",
      _cbrow(_cb_on, "gen_evasion_point")["cheated"] and _cb_on["cheats"] == 1)
check("cheatbench: il co-fuzzer kernel ABBASSA il cheating-rate misurato (2/6 -> 1/6)",
      _cb_off["cheats"] == 2 and _cb_on["cheats"] == 1)
# CLASSE A LIVELLO DI CANALE (recon 2026-06-05): il result-channel-hijack era un 7° buco reale NON misurato.
from substrate_core.cheatbench import measure_channel_attacks as _mca
_ca = _mca(key=b"cheatbench-key")
check("cheatbench: result-channel-hijack NAIVE (print/os._exit) CHIUSO dal nonce di isolamento-canale",
      _ca["result_channel_hijack"]["ground_truth_buggy"] and _ca["result_channel_hijack"]["closed"]
      and not _ca["result_channel_hijack"]["cheated"])
check("cheatbench (ONESTO): variante FRAME-WALK MISURATA e dichiarata RESIDUO FONDAMENTALE (non assunta zero)",
      _ca.get("result_channel_hijack_framewalk", {}).get("fundamental") is True
      and _ca["result_channel_hijack_framewalk"]["ground_truth_buggy"])

# TIER FORMALE (SMT/Z3, oracolo FIDATO) + ESECUTORE ISOLATO REALE (WASM, zero-capability) — le nuove fondamenta.
if "smt" in sc.REGISTRY and _have("z3"):
    _se = verify(Claim("smt", "board", "forall_property",
                       {"property_smt2": "(declare-const x (_ BitVec 8))(assert (= (bvadd x #x00) x))"}), key=KEY)
    check("SMT: forall x  x+0==x -> CONFIRMED/PROVEN (oracolo Z3 FIDATO, UNSAT-negazione: SOUND, non empirico)",
          _se["certificate"]["verdict"]["status"] == "CONFIRMED" and _se["certificate"]["verdict"]["assurance"] == "proven")
    _sr = verify(Claim("smt", "board", "forall_property",
                       {"property_smt2": "(declare-const x (_ BitVec 8))(assert (bvugt (bvadd x #x01) x))"}), key=KEY)
    check("SMT: x+1>x (overflow a 8 bit) -> REFUTED + controesempio RI-VERIFICATO sotto il model",
          _sr["certificate"]["verdict"]["status"] == "REFUTED" and (_sr["certificate"]["verdict"]["witness"] or {}).get("counterexample"))
    _sp = _submit({"domain": "smt", "target": "b", "kind": "forall_property",
                   "params": {"property_smt2": "(declare-const x Int)(assert (>= x 2))",
                              "status": "CONFIRMED", "assurance": "proven"}}, key=KEY)
    check("SMT prover-independence: asserire CONFIRMED su prop FALSA -> REFUTED (l'oracolo e' Z3, NON il prover)",
          _sp["certificate"]["verdict"]["status"] == "REFUTED")
else:
    results.append(("SMT tier formale (z3 assente -> SKIP)", None))
if "wasmprop" in sc.REGISTRY and _have("wasmtime"):
    _SQ = '(module (func (export "subject")(param i32)(result i32) local.get 0 local.get 0 i32.mul))'
    _CAP = ('(module (import "host" "escape" (func $e (param i32)(result i32)))'
            ' (func (export "subject")(param i32)(result i32) local.get 0 call $e))')
    _wb = verify(Claim("wasmprop", "board", "trusted_property", {"wat": _SQ, "property": "nonnegative", "domain": [-12, 12]}), key=KEY)
    check("WASM-isolato: square nonnegative su dominio finito -> CONFIRMED/BOUNDED (esaustivo, oracolo host-FIDATO)",
          _wb["certificate"]["verdict"]["status"] == "CONFIRMED" and _wb["certificate"]["verdict"]["assurance"] == "bounded")
    _wc = verify(Claim("wasmprop", "board", "trusted_property", {"wat": _CAP, "property": "nonnegative", "domain": [0, 3]}), key=KEY)
    check("WASM-isolato: modulo che RICHIEDE una capability host -> ZERO import -> ABSTAIN (frame-walk/host-escape impossibili PER COSTRUZIONE)",
          _wc["certificate"]["verdict"]["status"] == "ABSTAIN")
else:
    results.append(("WASM-isolato (wasmtime assente -> SKIP)", None))

# 4) firma HMAC: verifica + tamper-evidence
cd = e1["certificate"]
_vd = cd["verdict"]
cert = Certificate(Claim(**cd["claim"]),
                   Verdict(Status(_vd["status"]), _vd["executed"], _vd["reason"], _vd["witness"], _vd["reproduce"],
                           _vd.get("assurance", "none"), _vd.get("coverage", {}),
                           _vd.get("residual_risk"), _vd.get("assurance_caveat", "")), cd["engine"], cd["stamp"])
check("firma Ed25519 verifica con la CHIAVE PUBBLICA (no potere di conio)", verify_sig(cert, e1["sig"], e1["pubkey"]))
check("firma rifiuta una chiave pubblica SBAGLIATA", not verify_sig(cert, e1["sig"], sc.derive_pubkey(b"wrong-key")))
check("content_hash deterministico", sc.content_hash(cert) == e1["content_hash"])
check("L3.5 asimmetria: la pubkey nella busta == derive_pubkey(seed) (separata dalla privata di conio)",
      e1["pubkey"] == sc.derive_pubkey(KEY))
_forged = sc.envelope(cert, key=b"attacker-seed")   # un forger ri-firma lo STESSO cert con la PROPRIA chiave
check("L3.5 asimmetria: forger ri-firma con la propria chiave -> verifica SOLO sotto la SUA pubkey, RIFIUTATO sotto l'emittente",
      verify_sig(cert, _forged["sig"], sc.derive_pubkey(b"attacker-seed")) and not verify_sig(cert, _forged["sig"], e1["pubkey"]))

# L3.5 WRITE-GATE CRITTOGRAFICO: un grafo con pubkey FIDATA si difende (rigetta non-firmate / mal-firmate / manomesse)
_PUB = sc.derive_pubkey(KEY)
_gsec = CertGraph(pubkey=_PUB)
_gsec.ingest(e1)
check("L3.5 write-gate: busta firmata correttamente -> ACCETTATA nel grafo fidato", e1["content_hash"] in _gsec._certs)
_poison = _copy.deepcopy(e2); _poison["sig"] = "00" * 64    # firma spazzatura sotto la pubkey attesa
_rej_sig = False
try:
    _gsec.ingest(_poison)
except ProvenanceError:
    _rej_sig = True
check("L3.5 write-gate: firma Ed25519 NON valida -> ingest RIGETTATO (anti-poisoning della memoria)",
      _rej_sig and _poison["content_hash"] not in _gsec._certs)
_unsigned = sc.envelope(cert, key=None)                     # busta senza firma
_rej_uns = False
try:
    _gsec.ingest(_unsigned)
except ProvenanceError:
    _rej_uns = True
check("L3.5 write-gate: busta NON firmata -> RIGETTATA dal grafo fidato", _rej_uns)
_tampered = _copy.deepcopy(e1)
_tampered["certificate"]["verdict"]["reason"] = "CORPO MANOMESSO"   # cambia il corpo, NON l'hash dichiarato
_rej_hash = False
try:
    CertGraph().ingest(_tampered)                           # anche un grafo PERMISSIVO ricomputa l'hash
except ProvenanceError:
    _rej_hash = True
check("L3.5 write-gate: corpo manomesso (content_hash non torna) -> RIGETTATO anche dal grafo permissivo", _rej_hash)

# L3.5 MERKLE domain separation (CVE-2012-2459): foglia 0x00, nodo interno 0x01
import hashlib as _hl
from substrate_core.export import merkle_root as _mroot
_a, _b = "11" * 32, "22" * 32
check("L3.5 merkle: radice di 1 foglia = H(0x00||foglia) (domain separation applicata)",
      _mroot([_a]) == _hl.sha256(b"\x00" + bytes.fromhex(_a)).hexdigest())
check("L3.5 merkle: radice domain-separata != costruzione naive H(a||b) (CVE-2012-2459 mitigato)",
      _mroot([_a, _b]) != _hl.sha256(bytes.fromhex(_a) + bytes.fromhex(_b)).hexdigest())

# L3.5 EXPORT verificabile con la SOLA chiave pubblica (auditor terzo: autentica l'emittente, zero potere di conio)
_rep_pub = verify_bundle(load_bundle(_bp), pubkey=sc.derive_pubkey(KEY))
check("L3.5 export: il .scar si verifica con la SOLA pubkey (terzo autentica l'emittente, non puo' coniare)",
      _rep_pub["intact"] and _rep_pub["checks"].get("issuer_authenticated") and _rep_pub["checks"].get("sig_all_ok"))

# FIREHOSE (Pilastro 2): INGESTIONE CONTINUA. Uno stream -> verifica continua -> allarmi firmati -> .scar portabile.
from substrate_core.firehose import watch as _watch, export_alarms as _exp_alarms
_stream = [os.path.join(EX, "ex_abs.py"), os.path.join(EX, "ex_buggy_sort.py"), os.path.join(EX, "ex_vacuous.py")]
_fh = _watch(_stream, key=KEY)
check("FIREHOSE: stream verificato in CONTINUO (3 item: 1 CONFIRMED, 1 REFUTED, 1 ABSTAIN)",
      _fh["summary"]["seen"] == 3 and _fh["summary"]["confirmed"] == 1
      and _fh["summary"]["refuted"] == 1 and _fh["summary"]["abstain"] == 1)
check("FIREHOSE: l'item REFUTED diventa un ALLARME col witness firmato",
      len(_fh["alarms"]) == 1 and bool(_fh["alarms"][0]["witness"]) and "buggy" in _fh["alarms"][0]["item"])
check("FIREHOSE: il grafo del demone e' WRITE-GATED e INTEGRO (solo certs firmati validi, 3 ingeriti)",
      _fh["graph"].verify_integrity(key=KEY)["intact"] and len(_fh["graph"]._certs) == 3)
_fbundle = _exp_alarms(_fh["graph"], key=KEY, name="firehose-demo")
check("FIREHOSE: lo stato del demone si esporta come .scar firmato (verificabile da un terzo con la sola pubkey)",
      verify_bundle(_fbundle, pubkey=sc.derive_pubkey(KEY))["intact"])

# GITHUB GUARDIAN (Pilastro 2, adapter live): CI/CD zero-trust a falsi-positivi ZERO (auditor SCRIPTATO, no LLM)
from substrate_core.github_adapter import audit_source as _audit, format_alarm as _falarm, guardian as _guardian
from substrate_core.agent import ScriptedAuditor as _SA
_AUD = _SA(
    "def subject(x):\n    return running_max(x)\n",
    ("def prop(x, y):\n    if len(y) != len(x):\n        return False\n"
     "    return all(y[i] == max(x[:i+1]) for i in range(len(x)))\n"),
    "def gen(rng):\n    n = rng.randint(1, 6)\n    return [rng.randint(-5, 5) for _ in range(n)]\n")
_buggy_src = open(os.path.join(EX, "ex_commit_buggy.py"), encoding="utf-8").read()
_ok_src = open(os.path.join(EX, "ex_commit_ok.py"), encoding="utf-8").read()
_rb = _audit("ex_commit_buggy.py", _buggy_src, key=KEY, auditor=_AUD, contract="list[int]")
check("GUARDIAN: commit BUGGATO (off-by-one) -> REFUTED col controesempio ESEGUITO (allarme reale)",
      _rb["status"] == "REFUTED" and bool((_rb["verdict"]["witness"] or {}).get("input")))
check("GUARDIAN: l'allarme cita input/output ESEGUITO + content_hash (mai 'penso ci sia un bug')",
      "input =" in _falarm(_rb) and "content_hash" in _falarm(_rb))
_ro = _audit("ex_commit_ok.py", _ok_src, key=KEY, auditor=_AUD, contract="list[int]")
check("GUARDIAN: commit CORRETTO -> CONFIRMED, NESSUN allarme (falsi-positivi ZERO per costruzione)",
      _ro["status"] == "CONFIRMED")
_gd = _guardian([("ex_commit_buggy.py", _buggy_src), ("ex_commit_ok.py", _ok_src)], key=KEY, auditor=_AUD, contract="list[int]")
check("GUARDIAN: pipeline completa -> 1 ALLARME (solo buggy) + .scar firmato verificabile con la sola pubkey",
      len(_gd["alarms"]) == 1 and verify_bundle(_gd["scar"], pubkey=sc.derive_pubkey(KEY))["intact"])

# STELE DI ROSETTA (Sfida 2): equivalenza semantica TRANS-LINGUAGGIO (python ref vs javascript impl, via node)
import shutil as _sh
if "differential" in sc.REGISTRY and _sh.which("node"):
    _dm = verify(Claim("differential", os.path.join(EX, "ex_diff_modulo.py"), "equivalence",
                       {"impl_lang": "javascript", "contract": "int"}), key=KEY)
    _dmv = _dm["certificate"]["verdict"]
    check("ROSETTA: modulo dei negativi python vs JS -> REFUTED (divergenza ESEGUITA, non-equivalenza provata)",
          _dmv["status"] == "REFUTED" and _dmv["assurance"] == "proven")
    check("ROSETTA: il witness mostra l'input divergente + i due output diversi (la prova della regressione)",
          "input" in (_dmv["witness"] or {}) and any("output" in k for k in (_dmv["witness"] or {})))
    _de = verify(Claim("differential", os.path.join(EX, "ex_diff_equiv.py"), "equivalence",
                       {"impl_lang": "javascript", "contract": "int"}), key=KEY)
    _dev = _de["certificate"]["verdict"]
    check("ROSETTA: abs(x)+1 python vs JS -> CONFIRMED/empirical (equivalenza; regola-del-3, NON prova esaustiva)",
          _dev["status"] == "CONFIRMED" and _dev["assurance"] == "empirical" and isinstance(_dev.get("residual_risk"), (int, float)))
    _drg = CertGraph(pubkey=sc.derive_pubkey(KEY)); _drg.ingest(_de)
    check("ROSETTA: il cert di equivalenza e' WRITE-GATED+integro nel grafo (.scar portabile, offline-verificabile)",
          _drg.verify_integrity(key=KEY)["intact"])
else:
    results.append(("ROSETTA differential (node assente -> SKIP)", None))

# OVERLAY UNIVERSALE (Sfida 1): il code_hash canonico e' STABILE e robusto -> il content-script JS lo riproduce identico
from substrate_core.github_adapter import code_hash as _codehash
check("OVERLAY: code_hash canonico robusto a CRLF + trailing-whitespace (precondizione compat Python<->JS)",
      _codehash("def f():\n    return 1\n") == _codehash("def f():\r\n    return 1   \n\n"))
check("OVERLAY: code_hash distingue codice diverso (no collisione banale)",
      _codehash("def f():\n    return 1") != _codehash("def f():\n    return 2"))
# OVERLAY: estrazione ROBUSTA dal sorgente completo (fine dell'euristica) — gemello del content-script (worker_core.js)
from substrate_core.codeextract import extract_functions as _extract
_NOISY = ("import math\n# def NOPE(): un commento\nX = \"stringa con def fake():\"\n\n"
          "def a(x):\n    return x + 1\n\n"
          "def b(y):\n    \"\"\"\n    docstring multilinea che contiene\n    def inner(): che NON va estratta\n    \"\"\"\n    return y * 2\n")
_fx = _extract(_NOISY)
check("OVERLAY: estrattore robusto trova SOLO le funzioni reali (a, b), ignora def in commento/stringa/docstring-multilinea",
      [f["name"] for f in _fx] == ["a", "b"])
check("OVERLAY: granularita' per-funzione -> ogni funzione ha un code_hash distinto",
      len(_fx) == 2 and _codehash(_fx[0]["src"]) != _codehash(_fx[1]["src"]))

# 5) composizione SOUND
comp_bad = compose_bundle([e1, e2], "and", key=KEY)
check("compose_and(buono, rotto) -> REFUTED", comp_bad["certificate"]["verdict"]["status"] == "REFUTED")
e1b = verify(Claim("pyprop", os.path.join(EX, "ex_abs.py"), "invariant", {"trials": 200, "seed": 1}), key=KEY)
comp_ok = compose_bundle([e1, e1b], "and", key=KEY)
check("compose_and(buono, buono) -> CONFIRMED", comp_ok["certificate"]["verdict"]["status"] == "CONFIRMED")
check("composizione di empirical resta EMPIRICAL (anello debole)", comp_ok["certificate"]["verdict"]["assurance"] == "empirical")

# 6) organismo autonomo (sweep -> sistema)
res = sweep([(os.path.join(EX, "ex_abs.py"), "pyprop"), (os.path.join(EX, "ex_buggy_sort.py"), "pyprop")], key=KEY)
check("organismo sweep -> sistema REFUTED", res["system"]["certificate"]["verdict"]["status"] == "REFUTED")

# 7) ABSTAIN onesto (mai finto-verdetto)
e3 = verify(Claim("pyprop", os.path.join(EX, "NON_ESISTE.py"), "invariant", {}), key=KEY)
check("pyprop file mancante -> ABSTAIN", e3["certificate"]["verdict"]["status"] == "ABSTAIN")

# 8) erc4626 (forge) + composizione CROSS-DOMINIO
if "erc4626" in sc.REGISTRY and _shutil.which("forge"):
    try:
        import verivault
        g = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(verivault.__file__))), "gate")
        tg = os.path.join(g, "targets")
        ev = verify(Claim("erc4626", os.path.join(tg, "VaultBalanceOf.sol"), "immunity:donation_inflation",
                          {"gate": g, "result_key": "solmate_balanceof", "test": "test/GeneralGate.t.sol"}), key=KEY)
        check("erc4626 VaultBalanceOf -> REFUTED/VULN", ev["certificate"]["verdict"]["status"] == "REFUTED")
        check("erc4626 REFUTED -> assurance=proven (exploit eseguito)", ev["certificate"]["verdict"]["assurance"] == "proven")
        ei = verify(Claim("erc4626", os.path.join(tg, "OZVault.sol"), "immunity:donation_inflation",
                          {"gate": g, "result_key": "oz_offset0", "test": "test/GeneralGate.t.sol"}), key=KEY)
        check("erc4626 OZVault -> CONFIRMED/IMMUNE", ei["certificate"]["verdict"]["status"] == "CONFIRMED")
        check("erc4626 CONFIRMED -> assurance=bounded (sweep, non prova)", ei["certificate"]["verdict"]["assurance"] == "bounded")
        cross = compose_bundle([e1, ei], "and", key=KEY)   # Python + Solidity in UN sistema
        check("composizione CROSS-DOMINIO (py+sol) -> CONFIRMED", cross["certificate"]["verdict"]["status"] == "CONFIRMED")
        check("cross-dominio assurance = empirical (anello piu' debole tra empirical e bounded)", cross["certificate"]["verdict"]["assurance"] == "empirical")
    except Exception as ex:  # noqa
        check(f"erc4626 [errore: {type(ex).__name__}: {ex}]", False)
else:
    results.append(("erc4626 (forge/verivault assente -> SKIP)", None))

# board
print("=" * 64)
print("substrate_core - verify_all (green-board riproducibile)")
print("=" * 64)
failed = 0
for name, ok in results:
    tag = "PASS" if ok is True else ("SKIP" if ok is None else "FAIL")
    if ok is False:
        failed += 1
    print(f"  [{tag}] {name}")
print("=" * 64)
print("ALL GREEN" if failed == 0 else f"{failed} FAILED")
sys.exit(1 if failed else 0)
