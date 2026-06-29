"""Domini di verifica innestabili nel kernel substrate_core."""
# Auto-registrazione GRACEFUL dei domini built-in: ognuno chiama register() all'import. Le dipendenze opzionali
# (z3, wasmtime, greenery, ...) sono importate LAZY dentro i gate, quindi questi import non falliscono per esse;
# eventuali errori sono comunque ignorati per non rompere il package.
for _m in ("pyprop", "smt", "differential", "regex_equiv", "replay", "entity_probe", "erc4626", "wasmprop"):
    try:
        __import__(__name__ + "." + _m)
    except Exception:  # noqa
        pass
try:
    del _m
except Exception:  # noqa
    pass
