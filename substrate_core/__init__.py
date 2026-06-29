"""substrate_core — infrastruttura VERIFICATION-NATIVE domain-agnostic.

Kernel (claim falsificabile -> exec-gate -> certificato a 3 vie firmato/componibile) + domini pluggable.
La strada che ha superato OGNI cancello di falsificazione del progetto, generalizzata a infrastruttura.
"""
from .kernel import (  # noqa: F401
    Status, Claim, Verdict, Certificate, Domain,
    register, get_domain, verify,
    content_hash, canonical_json, sign, verify_sig, envelope, derive_pubkey, cert_from_dict,
    compose_and, compose_or, compose_bundle, REGISTRY,
)

from .cert_graph import CertGraph, ProvenanceError  # noqa: F401
from .temporal import scope, is_state_bound, compatible, is_live  # noqa: F401  (verita' a 4 dimensioni / TOCTOU)
from .ads import build_index, query, verify_query  # noqa: F401  (indice autenticato / query a completezza)
from .statelight import (  # noqa: F401  (kernel light-client / oracolo — pluggable)
    verify_inclusion, build_proof, ProofStore, verify_state_proof, verify_eth_mpt, PROOF_VERIFIERS)

from .pipeline import pipe  # noqa: F401  (passaggio di testimone proof-carrying)

# --- registra i domini built-in ---
from .domains import pyprop  # noqa: F401  (auto-registra "pyprop")
from .domains import replay  # noqa: F401  (auto-registra "replay" — esecutore witness-passing)
from .domains import entity_probe  # noqa: F401  (auto-registra "entity_probe" — ontologia proof-carrying)
from .domains import differential  # noqa: F401  (auto-registra "differential" — equivalenza trans-linguaggio / Stele di Rosetta)

# smt dipende da z3 (TIER FORMALE, oracolo fidato): import GUARDATO -> il kernel vive anche senza z3.
try:
    from .domains import smt  # noqa: F401  (auto-registra "smt" se z3 e' importabile — proven via UNSAT)
    _SMT = True
except Exception:  # noqa
    _SMT = False

# netacl_equiv dipende da z3 (equivalenza firewall/ACL stateless per QF_BV): import GUARDATO.
try:
    from .domains import netacl_equiv  # noqa: F401  (auto-registra "netacl_equiv" se z3 e' importabile)
    _NETACL = True
except Exception:  # noqa
    _NETACL = False

# wasmprop dipende da wasmtime (ESECUTORE ISOLATO REALE): import GUARDATO -> il kernel vive anche senza wasmtime.
try:
    from .domains import wasmprop  # noqa: F401  (auto-registra "wasmprop" — subject WASM zero-cap + oracolo host-fidato)
    _WASMPROP = True
except Exception:  # noqa
    _WASMPROP = False

# erc4626 dipende da verivault (forge): import GUARDATO, cosi' il kernel vive anche senza.
try:
    from .domains import erc4626  # noqa: F401  (auto-registra "erc4626" se verivault e' importabile)
    _ERC4626 = True
except Exception:  # noqa
    _ERC4626 = False

# STRATO ENTERPRISE (PERIFERIA, TCB puro -> kernel.py non li importa, firewall verde): SDK tier-aware, interop
# attestazioni in-toto/DSSE, policy/admission, content-address CIDv1, transparency-log, vettori di conformita'.
from . import sdk, attest, policy, cid, conformance, transparency, vcache, cicd  # noqa: F401

__all__ = [
    "Status", "Claim", "Verdict", "Certificate", "Domain",
    "register", "get_domain", "verify",
    "content_hash", "canonical_json", "sign", "verify_sig", "envelope", "derive_pubkey", "cert_from_dict",
    "compose_and", "compose_or", "compose_bundle", "REGISTRY",
    "sdk", "attest", "policy", "cid", "conformance", "transparency", "vcache", "cicd",
]
