"""substrate_core.vcache — CACHE di verdetti CONTENT-ADDRESSED con AUDIT di ri-esecuzione (scale/ops world-class
SENZA perdere soundness). La chiave lega OGNI input che determina il verdetto: canonical(claim) + il DIGEST DEL
CONTENUTO del target (non il path) -> se il target cambia, la chiave cambia -> ZERO verdetti stantii. Un AUDIT
CAMPIONATO ri-esegue e confronta: una HIT il cui ri-calcolo DISSENTE = cache AVVELENATA/stantia -> CacheUnsound
(la voce e' espulsa e il chiamante avvisato). PERIFERIA (kernel.py resta puro)."""
from __future__ import annotations

import hashlib
import json
import os
import random

from .kernel import Claim, verify


class CacheUnsound(Exception):
    """Una HIT di cache il cui ri-calcolo DISSENTE dal valore memorizzato -> cache avvelenata/stantia (kill-gate)."""


def _target_digest(target: str) -> str:
    """Digest del CONTENUTO del target (file -> sha256 dei byte; altrimenti del literal). Lega il verdetto al contenuto."""
    try:
        if target and os.path.exists(target):
            with open(target, "rb") as f:
                return "file:" + hashlib.sha256(f.read()).hexdigest()
    except Exception:  # noqa
        pass
    return "lit:" + hashlib.sha256(str(target).encode("utf-8")).hexdigest()


def cache_key(claim: Claim) -> str:
    """Chiave content-addressed: lega dominio+kind+params(canonico)+digest-contenuto-del-target. Deterministica."""
    body = json.dumps({"domain": claim.domain, "kind": claim.kind, "params": claim.params,
                       "target_digest": _target_digest(claim.target)},
                      sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class VerdictCache:
    def __init__(self, *, key=None, audit_rate: float = 0.05, seed: int = 0):
        self._store = {}
        self._sign_key = key
        self.audit_rate = audit_rate
        self._rng = random.Random(seed)
        self.hits = self.misses = self.audits = self.audit_fail = 0

    @staticmethod
    def _vt(env):
        v = env["certificate"]["verdict"]
        return (v["status"], v.get("assurance"))

    def get_or_verify(self, claim: Claim, *, force_audit: bool = False):
        """Ritorna il verdetto (cache HIT) o lo calcola (MISS). Con prob audit_rate (o force_audit) ri-esegue e
        confronta una HIT: un disaccordo solleva CacheUnsound (cache avvelenata) -> mai servire un verdetto falso."""
        k = cache_key(claim)
        cached = self._store.get(k)
        if cached is not None:
            self.hits += 1
            if force_audit or self._rng.random() < self.audit_rate:
                self.audits += 1
                fresh = verify(claim, key=self._sign_key)
                if self._vt(fresh) != self._vt(cached):
                    self.audit_fail += 1
                    self._store.pop(k, None)
                    raise CacheUnsound(f"cache AVVELENATA su {k[:12]}: memorizzato {self._vt(cached)} != "
                                       f"ri-eseguito {self._vt(fresh)} -> voce espulsa")
                return fresh    # audit superato: ritorna il fresco (rinfresca anche la voce)
            return cached
        self.misses += 1
        env = verify(claim, key=self._sign_key)
        self._store[k] = env
        return env

    def poison(self, claim: Claim, fake_env: dict) -> None:
        """SOLO-TEST: inietta un verdetto falso (per provare che l'audit lo CATTURA)."""
        self._store[cache_key(claim)] = fake_env

    def stats(self) -> dict:
        return {"hits": self.hits, "misses": self.misses, "audits": self.audits,
                "audit_fail": self.audit_fail, "size": len(self._store)}
