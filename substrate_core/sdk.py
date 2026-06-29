"""substrate_core.sdk — facade pulita e TIER-AWARE sopra il kernel (SPEC v0.1.0).

Tre modi di provare un claim, con la loro forza ONESTA (vedi SPEC.md §3, §7):
  prove_smt(smt2)             -> PROVEN  (oracolo Z3 FIDATO; sound sulla teoria decisa)
  prove_wasm(wat, property=)  -> BOUNDED|EMPIRICAL (subject WASM ISOLATO zero-cap; oracolo host-FIDATO)
  prove_pyprop(path)          -> EMPIRICAL (bug-finder IN-PROCESS; oracolo scritto dal PROVER -> NON sound)
+ to_scar/verify_scar per la portabilita' trustless; status()/tier()/is_sound_confirm() per leggere il verdetto.

is_sound_confirm() incastona la disciplina nel codice: un CONFIRMED 'empirical' (oracolo del prover) NON e' sound;
solo bounded/proven-spec/proven (oracolo fidato / esaustivo / inclusion-proof) lo sono. L'SDK e' PERIFERIA, non TCB."""
from __future__ import annotations

from typing import Optional, List

from .kernel import Claim, verify, derive_pubkey
from .export import export_bundle, save_bundle, load_bundle, verify_bundle
from .cert_graph import CertGraph

SPEC_VERSION = "0.1.0"

_SOUND_CONFIRM_TIERS = ("bounded", "proven-spec", "proven")


def status(env: dict) -> str:
    return env["certificate"]["verdict"]["status"]


def tier(env: dict) -> str:
    return env["certificate"]["verdict"].get("assurance", "none")


def is_sound_confirm(env: dict) -> bool:
    """True SSE il verdetto e' un CONFIRMED la cui forza NON dipende da un oracolo scritto dal prover.
    SOUND: tier in {bounded, proven-spec, proven} (Z3 / host-property / esaustivo / inclusion-proof).
    NON-SOUND (bug-finder): tier == empirical (oracolo del prover; SPEC §7)."""
    v = env["certificate"]["verdict"]
    return v["status"] == "CONFIRMED" and v.get("assurance") in _SOUND_CONFIRM_TIERS


def prove_smt(property_smt2: str, *, key: Optional[bytes] = None, timeout_ms: int = 5000) -> dict:
    """Prova ∀ una proprieta' (SMT-LIB2), oracolo Z3 FIDATO. UNSAT-negazione -> CONFIRMED/PROVEN; model -> REFUTED."""
    return verify(Claim("smt", "sdk", "forall_property",
                        {"property_smt2": property_smt2, "timeout_ms": timeout_ms}), key=key)


def prove_wasm(*, wat: Optional[str] = None, wasm_hex: Optional[str] = None, property: str,
               domain=None, export: str = "subject", key: Optional[bytes] = None) -> dict:
    """Esegue un subject WASM ISOLATO (zero-capability, fuel) contro una proprieta' host-FIDATA (per nome).
    domain finito dichiarato -> BOUNDED (esaustivo); altrimenti EMPIRICAL (campione)."""
    p = {"property": property, "export": export}
    if wat:
        p["wat"] = wat
    if wasm_hex:
        p["wasm_hex"] = wasm_hex
    if domain is not None:
        p["domain"] = domain
    return verify(Claim("wasmprop", "sdk", "trusted_property", p), key=key)


def prove_pyprop(path: str, *, contract: str = "", key: Optional[bytes] = None) -> dict:
    """Fuzz IN-PROCESS di subject/prop/gen del prover. BUG-FINDER (EMPIRICAL): oracolo del prover -> NON sound (SPEC §7)."""
    p = {"contract": contract} if contract else {}
    return verify(Claim("pyprop", path, "invariant", p), key=key)


def to_scar(envs: List[dict], path: str, *, key: bytes, name: str = "sdk-bundle") -> dict:
    """Impacchetta buste-certificato in un .scar firmato, portabile, verificabile OFFLINE da un terzo (solo pubkey)."""
    g = CertGraph(pubkey=derive_pubkey(key))
    for e in envs:
        g.ingest(e)
    bundle = export_bundle(g, key=key, name=name)
    save_bundle(bundle, path)
    return bundle


def verify_scar(path: str, *, pubkey: str) -> dict:
    """Verifica un .scar con la SOLA chiave pubblica (autentica l'emittente, NON puo' coniare). Ritorna il report."""
    return verify_bundle(load_bundle(path), pubkey=pubkey)
