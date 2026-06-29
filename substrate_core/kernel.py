"""substrate_core.kernel — infrastruttura VERIFICATION-NATIVE, domain-agnostic.

Il principio che ha SUPERATO ogni cancello di falsificazione di questo progetto (6 round, 3 filoni):

  Un CLAIM e' falsificabile. Un GATE lo adjudica PER ESECUZIONE, con esito a 3 vie:
    REFUTED   = controesempio ESEGUITO (il claim e' FALSO) + witness ri-eseguibile
    CONFIRMED = evidenza ESEGUITA che il claim regge (prova/N-trial) + witness
    ABSTAIN   = non adjudicabile, ragione TIPATA (mai un finto-verdetto)
  I certificati sono firmati, content-hashed, portabili, ri-eseguibili, e COMPONGONO.

I DOMINI si innestano (schema-claim + generatore-harness + gate-esecuzione). Il kernel resta agnostico.
Questo file non dipende da alcun dominio: e' il substrato.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class Status(str, Enum):
    REFUTED = "REFUTED"      # claim falso, con controesempio eseguito
    CONFIRMED = "CONFIRMED"  # claim retto da esecuzione (prova/trial)
    ABSTAIN = "ABSTAIN"      # non adjudicabile (mai finto-verdetto)


@dataclass
class Claim:
    """Una proprieta' FALSIFICABILE su un target."""
    domain: str
    target: str
    kind: str
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"domain": self.domain, "target": self.target, "kind": self.kind, "params": self.params}


# ASSURANCE LATTICE — quanto e' FORTE il verdetto, ORTOGONALE allo status, STRETTAMENTE ORDINATO.
# La critica chiave: "non ho trovato controesempi in N trial" != "vale per ogni input". Nominare la scala
# (principio Common Criteria EAL / DO-178C DAL: il tier piu' alto DOMINA) rende l'overclaim STRUTTURALMENTE
# impossibile. Ogni tier nomina il suo METODO e la sua copertura; la composizione prende sempre il piu' debole.
NONE = "none"                # nessuna evidenza (ABSTAIN)
EMPIRICAL = "empirical"      # CAMPIONATO (fuzz): nessun controesempio in N trial -> rischio-residuo STIMATO, NON prova
BOUNDED = "bounded"          # ESAUSTIVO su uno SPAZIO DEFINITO (sweep / bound k) -> sound dentro k, non generale
PROVEN_SPEC = "proven-spec"  # SIMBOLICO UNSAT entro bound k -> tutti gli input fino a k (col bound dichiarato)
PROVEN = "proven"            # SOUND: controesempio ESEGUITO, oppure esaustivo sul dominio dichiarato
PROOF = PROVEN               # alias retro-compatibile (codice/certificati esistenti che usano "proof"->"proven")

_ASSURANCE_RANK = {NONE: 0, EMPIRICAL: 1, BOUNDED: 2, PROVEN_SPEC: 3, PROVEN: 4}


def weakest(assurances: List[str]) -> str:
    """L'anello piu' debole governa: un sistema composto e' forte quanto la sua componente piu' debole."""
    if not assurances:
        return NONE
    return min(assurances, key=lambda a: _ASSURANCE_RANK.get(a, 0))


@dataclass
class Verdict:
    status: Status
    executed: bool                       # il gate ha DAVVERO girato? (no -> sospetto)
    reason: str = ""
    witness: Dict[str, Any] = field(default_factory=dict)   # controesempio OPPURE prova
    reproduce: str = ""                  # ricetta/comando per ri-eseguire il witness
    assurance: str = NONE                # tier del lattice -> FORZA del verdetto (anti-overclaim)
    coverage: Dict[str, Any] = field(default_factory=dict)  # cosa e' stato DAVVERO controllato (metodo, trial, spazio)
    residual_risk: Optional[float] = None  # per EMPIRICAL: stima del rischio non-coperto (es. regola-del-3: 3/N)
    assurance_caveat: str = ""           # SEMPRE con la stima: assunzioni + "sottostima se blackbox/non-uniforme"

    def to_dict(self) -> dict:
        return {"status": self.status.value, "executed": self.executed, "reason": self.reason,
                "witness": self.witness, "reproduce": self.reproduce,
                "assurance": self.assurance, "coverage": self.coverage,
                "residual_risk": self.residual_risk, "assurance_caveat": self.assurance_caveat}


@dataclass
class Certificate:
    claim: Claim
    verdict: Verdict
    engine: str = ""        # identita'/versione del gate che ha adjudicato
    stamp: str = ""         # timestamp passato dal chiamante (escluso dal content_hash)

    def to_dict(self) -> dict:
        return {"claim": self.claim.to_dict(), "verdict": self.verdict.to_dict(),
                "engine": self.engine, "stamp": self.stamp}


# --------------------------------------------------------------------------------------
# Certificato: hashing deterministico + firma + busta portabile
# --------------------------------------------------------------------------------------

def _canonical(cert: Certificate) -> str:
    """JSON canonico per il content_hash: deterministico, ESCLUDE stamp/firma (contestabile)."""
    d = cert.to_dict()
    d.pop("stamp", None)
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def content_hash(cert: Certificate) -> str:
    return hashlib.sha256(_canonical(cert).encode("utf-8")).hexdigest()


def canonical_json(cert: Certificate) -> str:
    """La stringa CANONICA esatta su cui si calcola content_hash. La incastoniamo nel .scar (export embed_canonical)
    per la verifica CROSS-LINGUAGGIO: un browser fa SHA-256 di QUESTI byte senza re-implementare il JSON di Python
    (che distingue 1.0 da 1, distinzione che JSON.parse in JS perde). I byte firmati viaggiano con la prova."""
    return _canonical(cert)


# --- FIRMA ASIMMETRICA Ed25519 -------------------------------------------------------------------------
# Il `key` (bytes, qualsiasi lunghezza) e' un SEED che deriva DETERMINISTICAMENTE una coppia Ed25519:
#   - chiave PRIVATA = autorita' di CONIO (solo chi possiede il seed firma un certificato valido);
#   - chiave PUBBLICA = capacita' di VERIFICA (viaggia col .scar; chi la possiede verifica ma NON puo' coniare).
# Separare il potere di coniare da quello di verificare e' tutto il punto: con HMAC (simmetrico) per far verificare
# un auditor dovevi dargli la chiave -> da quell'istante poteva forgiare a tuo nome. Con Ed25519 no.

def _privkey_from_seed(seed: bytes):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    if isinstance(seed, str):
        seed = seed.encode("utf-8")
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(bytes(seed)).digest())   # seed -> 32 byte deterministici


def derive_pubkey(seed: bytes) -> str:
    """Chiave pubblica (hex, raw-32B) derivata dal seed di firma. Va nel .scar: basta per VERIFICARE, non per coniare."""
    from cryptography.hazmat.primitives import serialization
    pub = _privkey_from_seed(seed).public_key()
    return pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def _pubkey_obj(pubkey):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if hasattr(pubkey, "verify"):
        return pubkey
    raw = bytes.fromhex(pubkey) if isinstance(pubkey, str) else bytes(pubkey)
    return Ed25519PublicKey.from_public_bytes(raw)


def sign(cert: Certificate, key: bytes) -> str:
    """Firma Ed25519 del content_hash con la chiave PRIVATA derivata dal seed. Solo il detentore del seed conia."""
    return _privkey_from_seed(key).sign(content_hash(cert).encode("utf-8")).hex()


def verify_sig(cert: Certificate, sig: Optional[str], pubkey) -> bool:
    """Verifica la firma con la chiave PUBBLICA (nessun potere di conio). `pubkey` = hex/bytes della pubkey,
    tipicamente quella EMBEDDED nel .scar o quella ATTESA/pubblicata dall'emittente. Mai un'eccezione -> bool."""
    if not sig or not pubkey:
        return False
    try:
        _pubkey_obj(pubkey).verify(bytes.fromhex(sig), content_hash(cert).encode("utf-8"))
        return True
    except Exception:  # noqa  (firma invalida / pubkey errata / sig malformata)
        return False


def cert_from_dict(cd: dict) -> Certificate:
    """Ricostruisce un Certificate dalla forma serializzata (per ri-hash + verifica-firma al confine ingest/load)."""
    vd = cd["verdict"]
    return Certificate(
        Claim(**cd["claim"]),
        Verdict(Status(vd["status"]), vd.get("executed", False), vd.get("reason", ""), vd.get("witness", {}) or {},
                vd.get("reproduce", ""), vd.get("assurance", NONE), vd.get("coverage", {}) or {},
                vd.get("residual_risk"), vd.get("assurance_caveat", "")),
        cd.get("engine", ""), cd.get("stamp", ""))


def envelope(cert: Certificate, key: Optional[bytes] = None, stamp: str = "") -> dict:
    """Busta firmata portabile: {certificate, content_hash, alg, sig, pubkey}. La pubkey viaggia con la busta:
    un verificatore terzo (col .scar + la pubkey ATTESA dell'emittente) verifica OFFLINE senza poter coniare."""
    if stamp:
        cert.stamp = stamp
    ch = content_hash(cert)
    return {
        "certificate": cert.to_dict(),
        "content_hash": ch,
        "alg": "ed25519",
        "sig": (sign(cert, key) if key else None),
        "pubkey": (derive_pubkey(key) if key else None),
    }


# --------------------------------------------------------------------------------------
# Dominio plugin + registro
# --------------------------------------------------------------------------------------

@dataclass
class Domain:
    """Un dominio di verifica innestabile."""
    name: str
    gate: Callable[[Claim], Verdict]                  # esegue e adjudica
    claim_templates: Callable[[str], List[Claim]] = None  # dato un target -> claim candidati (per l'organismo)
    describe: str = ""


REGISTRY: Dict[str, Domain] = {}


def register(domain: Domain) -> None:
    REGISTRY[domain.name] = domain


def get_domain(name: str) -> Domain:
    if name not in REGISTRY:
        raise KeyError(f"dominio non registrato: {name!r} (disponibili: {sorted(REGISTRY)})")
    return REGISTRY[name]


# --------------------------------------------------------------------------------------
# Entrypoint: adjudica un claim -> busta certificata
# --------------------------------------------------------------------------------------

def verify(claim: Claim, *, key: Optional[bytes] = None, stamp: str = "") -> dict:
    """Adjudica UN claim tramite il gate del suo dominio. TOTALE: input ignoto/spazzatura -> ABSTAIN, mai crash,
    mai un finto-verdetto. (Prover-independence: un prover NON-FIDATO che sottomette spazzatura ottiene ABSTAIN.)"""
    try:
        dom = get_domain(claim.domain)
    except KeyError:
        cert = Certificate(claim=claim, engine="kernel", stamp=stamp,
                           verdict=Verdict(Status.ABSTAIN, executed=False,
                                           reason=f"dominio sconosciuto: {claim.domain!r}"))
        return envelope(cert, key=key, stamp=stamp)
    try:
        verdict = dom.gate(claim)
    except Exception as e:  # un gate che esplode -> ABSTAIN onesto (non un finto-verdetto)
        verdict = Verdict(Status.ABSTAIN, executed=False, reason=f"gate ha sollevato: {type(e).__name__}: {e}")
    cert = Certificate(claim=claim, verdict=verdict, engine=dom.name, stamp=stamp)
    return envelope(cert, key=key, stamp=stamp)


# --------------------------------------------------------------------------------------
# Algebra di COMPOSIZIONE (sound) — il pezzo rivoluzionario: i certificati compongono
# --------------------------------------------------------------------------------------

def compose_and(verdicts: List[Verdict]) -> Verdict:
    """Congiunzione (un sistema regge IFF tutti i sotto-claim reggono).
       - REFUTED se QUALSIASI sotto-claim e' REFUTED (un controesempio refuta la congiunzione) + propaga il witness
       - CONFIRMED solo se TUTTI CONFIRMED (ed eseguiti)
       - altrimenti ABSTAIN (propagazione onesta dell'incertezza)
    Sound: una refutazione di un componente refuta il tutto; la conferma richiede tutti."""
    refs = [v for v in verdicts if v.status == Status.REFUTED]
    if refs:
        w = refs[0]
        return Verdict(Status.REFUTED, executed=w.executed,
                       reason=f"composizione REFUTED: {len(refs)}/{len(verdicts)} componenti falsi",
                       witness=w.witness, reproduce=w.reproduce,
                       assurance=w.assurance, coverage={"refuted_by": len(refs)})
    if verdicts and all(v.status == Status.CONFIRMED and v.executed for v in verdicts):
        link = weakest([v.assurance for v in verdicts])   # l'anello piu' debole governa l'assurance del sistema
        return Verdict(Status.CONFIRMED, executed=True,
                       reason=f"composizione CONFIRMED: {len(verdicts)}/{len(verdicts)} componenti retti "
                              f"(assurance di sistema = anello piu' debole = {link})",
                       witness={"n_components": len(verdicts)},
                       assurance=link, coverage={"components": len(verdicts),
                                                 "assurances": [v.assurance for v in verdicts]})
    n_abs = sum(1 for v in verdicts if v.status == Status.ABSTAIN)
    return Verdict(Status.ABSTAIN, executed=False,
                   reason=f"composizione ABSTAIN: {n_abs}/{len(verdicts)} non adjudicati (nessun controesempio)")


def compose_or(verdicts: List[Verdict]) -> Verdict:
    """Disgiunzione (almeno un claim regge). CONFIRMED se uno CONFIRMED; REFUTED se TUTTI REFUTED; else ABSTAIN."""
    confs = [v for v in verdicts if v.status == Status.CONFIRMED and v.executed]
    if confs:
        best = max(confs, key=lambda v: _ASSURANCE_RANK.get(v.assurance, 0))   # il migliore basta per una disgiunzione
        return Verdict(Status.CONFIRMED, executed=True, reason="disgiunzione CONFIRMED (>=1 componente retto)",
                       witness=best.witness, assurance=best.assurance)
    if verdicts and all(v.status == Status.REFUTED for v in verdicts):
        return Verdict(Status.REFUTED, executed=all(v.executed for v in verdicts),
                       reason="disgiunzione REFUTED (tutti i componenti falsi)", witness=verdicts[0].witness,
                       assurance=weakest([v.assurance for v in verdicts]))
    return Verdict(Status.ABSTAIN, executed=False, reason="disgiunzione ABSTAIN")


def compose_bundle(envelopes: List[dict], op: str = "and", *, key: Optional[bytes] = None, stamp: str = "") -> dict:
    """Compone una lista di BUSTE in un singolo certificato-di-sistema (ri-firmato, ri-hashed).
    TOCTOU: rispetta l'asse TEMPORALE — non si compongono certificati su STATI mutati incompatibili."""
    # COMPOSIZIONE TEMPORALE: raccogli i contesti (chain_id, state_root); >1 stato distinto -> non componibile.
    _ctxs = [((e.get("certificate", {}).get("claim", {}) or {}).get("params", {}) or {}).get("context") for e in envelopes]
    _keys = {(c.get("chain_id"), c.get("state_root")) for c in _ctxs if c is not None}
    if len(_keys) > 1:
        claim = Claim(domain="composite", target=f"{op}({len(envelopes)} certs)", kind=f"compose_{op}",
                      params={"temporal_conflict": sorted(str(k) for k in _keys),
                              "child_hashes": [e.get("content_hash") for e in envelopes]})
        v = Verdict(Status.ABSTAIN, executed=False,
                    reason=f"temporal-mismatch (TOCTOU): {len(_keys)} stati incompatibili -> non componibili sull'asse temporale")
        return envelope(Certificate(claim=claim, verdict=v, engine="substrate_core.compose", stamp=stamp), key=key, stamp=stamp)
    _shared_ctx = next((c for c in _ctxs if c is not None), None)

    verdicts = []
    for env in envelopes:
        vd = env["certificate"]["verdict"]
        verdicts.append(Verdict(Status(vd["status"]), executed=vd.get("executed", False),
                                reason=vd.get("reason", ""), witness=vd.get("witness", {}) or {},
                                reproduce=vd.get("reproduce", ""),
                                assurance=vd.get("assurance", NONE), coverage=vd.get("coverage", {}) or {},
                                residual_risk=vd.get("residual_risk"), assurance_caveat=vd.get("assurance_caveat", "")))
    composed = compose_and(verdicts) if op == "and" else compose_or(verdicts)
    targets = [env["certificate"]["claim"]["target"] for env in envelopes]
    claim = Claim(domain="composite", target=f"{op}({len(envelopes)} certs)", kind=f"compose_{op}",
                  params={"components": targets, "child_hashes": [e["content_hash"] for e in envelopes],
                          "context": _shared_ctx})   # il sistema EREDITA lo scope temporale condiviso
    cert = Certificate(claim=claim, verdict=composed, engine="substrate_core.compose", stamp=stamp)
    return envelope(cert, key=key, stamp=stamp)
