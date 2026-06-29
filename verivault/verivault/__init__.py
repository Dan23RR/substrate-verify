"""VeriVault — verification-native audit per ERC-4626 share-inflation (mattone F0 di Verifier Labs).
API: audit(sol_path), audit_immunity_demo(); schemas Claim/Verdict/Certificate; oracoli pluggabili."""
from .schemas import Claim, Verdict, Certificate, Status
from .pipeline import (audit, audit_realcode, audit_onchain, audit_signed,
                       audit_immunity_demo, build_default_registry)

__all__ = ["Claim", "Verdict", "Certificate", "Status", "audit", "audit_realcode",
           "audit_onchain", "audit_signed", "audit_immunity_demo", "build_default_registry"]
__version__ = "0.0.1"
