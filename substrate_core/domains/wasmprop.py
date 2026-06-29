"""substrate_core.domains.wasmprop — ESECUTORE ISOLATO REALE (WASM/wasmtime) + ORACOLO FIDATO host-side.

Chiude frame-walk E host-escape PER COSTRUZIONE (la stessa radice, la stessa cura): il `subject` del prover gira
in un guest WebAssembly con ZERO import -> nessuna capability (niente fd/frame/syscall HOST raggiungibili: un
guest WASM non ha sys._getframe sul processo host ne' può sintetizzare una syscall non concessa), sotto un budget
di FUEL deterministico (loop infinito -> Trap, cross-platform, NON dipende dal wall-clock come il timeout POSIX).
La PROPRIETA' e' FIDATA (libreria host, NON scritta dal prover) -> niente oracle-control: questa e' la differenza
che rende il verdetto SOUND, non solo isolato.

Tier ONESTO: dominio finito DICHIARATO ed ESAUSTIVO -> BOUNDED (sound entro il dominio); campionato -> EMPIRICAL.
NON nel TCB: wasmtime vive QUI in periferia; kernel.py resta puro (il firewall-test lo prova)."""
from __future__ import annotations

import time

from ..kernel import Claim, Verdict, Status, Domain, register, BOUNDED, EMPIRICAL, PROVEN

_MAX_EXHAUSTIVE = 65536         # cap il dominio esaustivo (anti wall-clock DoS); oltre -> campione
FUEL_FLOOR = 5_000_000          # il KERNEL fissa il fuel (il prover non puo' abbassarlo per sopprimere una refutazione)
_MEM_CAP = 64 * 1024 * 1024     # cap memoria del guest (anti memory.grow -> host-OOM / DoS)
_WALL_BUDGET = 20.0             # budget wall-clock totale del gate (anti DoS); sforato -> ABSTAIN, mai CONFIRMED
_EDGE = [0, 1, -1, 2, -2, 7, -7, 127, -128, 255, -256, 1000, -1000, 2 ** 31 - 1, -(2 ** 31)]


def _trusted_property(name):
    """ORACOLO FIDATO (host-side): mappa un NOME a un predicato. Il prover SCEGLIE il nome, non scrive l'oracolo.
    Ritorna (kind, fn): kind 'unary' fn(x,y)->bool ; 'idem' usa subject(y) ; 'invol' usa subject(y)==x ; 'seq' su (x,y) ordinati."""
    if name == "nonnegative":
        return ("unary", lambda x, y: y >= 0)
    if name == "monotonic_nondecreasing":
        return ("seq", None)
    if name == "idempotent":
        return ("idem", None)
    if name == "involutive":
        return ("invol", None)
    if name.startswith("bounded:"):
        try:
            _, lo, hi = name.split(":"); lo, hi = int(lo), int(hi)
            return ("unary", lambda x, y, lo=lo, hi=hi: lo <= y <= hi)
        except Exception:  # noqa
            return (None, None)
    if name.startswith("equals_const:"):
        try:
            c = int(name.split(":", 1)[1])
            return ("unary", lambda x, y, c=c: y == c)
        except Exception:  # noqa
            return (None, None)
    return (None, None)


def gate(claim: Claim) -> Verdict:
    try:
        import wasmtime
    except Exception as e:  # noqa
        return Verdict(Status.ABSTAIN, executed=False, reason=f"wasmtime non disponibile: {type(e).__name__}")
    p = claim.params or {}
    wat, wasm_hex, export, prop = p.get("wat"), p.get("wasm_hex"), p.get("export", "subject"), p.get("property", "")
    if not (wat or wasm_hex) or not prop:
        return Verdict(Status.ABSTAIN, executed=False, reason="manca wat/wasm_hex o property (nome dell'oracolo FIDATO)")
    kind, pred = _trusted_property(prop)
    if kind is None:
        return Verdict(Status.ABSTAIN, executed=False,
                       reason=f"property '{prop}' non e' nella libreria FIDATA (l'oracolo non si fida del prover)")
    try:
        fuel = max(int(p.get("fuel", FUEL_FLOOR)), FUEL_FLOOR)   # FLOOR: il prover non sceglie un fuel-suppressivo
    except Exception:  # noqa
        fuel = FUEL_FLOOR

    cfg = wasmtime.Config(); cfg.consume_fuel = True
    eng = wasmtime.Engine(cfg)
    try:
        module = wasmtime.Module(eng, wat if wat else bytes.fromhex(wasm_hex))
    except Exception as e:  # noqa
        return Verdict(Status.ABSTAIN, executed=True, reason=f"modulo WASM non compilabile: {type(e).__name__}: {e}")

    # IL KERNEL sceglie gli input: dominio finito DICHIARATO -> ESAUSTIVO (BOUNDED); altrimenti edge + campione (EMPIRICAL).
    dom = p.get("domain")
    exhaustive = False
    if isinstance(dom, (list, tuple)) and len(dom) == 2:
        lo, hi = int(dom[0]), int(dom[1])
        if 0 <= hi - lo + 1 <= _MAX_EXHAUSTIVE:
            inputs, exhaustive = list(range(lo, hi + 1)), True
        else:
            import random
            rng = random.Random(0)
            inputs = sorted(set(_EDGE + [rng.randint(lo, hi) for _ in range(2000)]))
    else:
        inputs = sorted(set(_EDGE))

    def call(x):
        st = wasmtime.Store(eng); st.set_fuel(fuel)
        try:
            st.set_limits(memory_size=_MEM_CAP)     # cap memoria del guest (anti memory.grow -> host-OOM)
        except Exception:  # noqa
            pass
        inst = wasmtime.Instance(st, module, [])    # ZERO import -> nessuna capability host
        fn = inst.exports(st).get(export)
        if fn is None:
            raise KeyError(f"export '{export}' mancante")
        return fn(st, x)

    # COPERTURA SOUND (recon 2026-06-05, red-team): un TRAP su un input del dominio significa che quell'input NON e'
    # stato valutato (fuel/unreachable/div0/mem). Un subject che TRAPPA esattamente l'input 'cattivo' lo nasconderebbe
    # -> NON e' un pass. Regola: un controesempio trovato -> REFUTED (sound); altrimenti QUALSIASI trap o budget-tempo
    # sforato -> ABSTAIN (copertura incompleta); solo una valutazione SENZA trap puo' dare CONFIRMED.
    t0 = time.monotonic()
    pairs, traps, trapped = [], 0, []
    witness, timed_out = None, False
    for x in inputs:
        if time.monotonic() - t0 > _WALL_BUDGET:
            timed_out = True; break
        try:
            y = call(x)
        except Exception:  # noqa  (Trap: input NON valutato)
            traps += 1; trapped.append(x); continue
        pairs.append((x, y))
        if kind == "unary" and not pred(x, y):
            witness = {"input": x, "output": y, "rule": prop}; break
        if kind in ("idem", "invol"):
            try:
                y2 = call(y)                          # 2a chiamata parte della valutazione di x
            except Exception:  # noqa  (la 2a chiamata TRAPPA -> x NON pienamente valutato: NON ingoiare)
                traps += 1; trapped.append(x); pairs.pop(); continue
            if kind == "idem" and y2 != y:
                witness = {"input": x, "output": y, "subject_of_output": y2, "rule": "idempotent"}; break
            if kind == "invol" and y2 != x:
                witness = {"input": x, "output": y, "subject_of_output": y2, "rule": "involutive"}; break
    if witness is None and kind == "seq":
        ordered = sorted(pairs, key=lambda t: t[0])
        for (x0, y0), (x1, y1) in zip(ordered, ordered[1:]):
            if not (y0 <= y1):
                witness = {"input_pair": [x0, x1], "output_pair": [y0, y1], "rule": "monotonic_nondecreasing"}; break

    if witness is not None:
        return Verdict(Status.REFUTED, executed=True,
                       reason=f"WASM-isolato: la proprieta' FIDATA '{prop}' e' VIOLATA (controesempio eseguito nel guest)",
                       witness=witness, reproduce=f"wasmtime: subject({witness.get('input', witness.get('input_pair'))}) (zero-cap, fuel={fuel})",
                       assurance=PROVEN,   # un controesempio ESEGUITO e' sound
                       coverage={"method": "WASM zero-cap + oracolo host-fidato", "isolated": True})
    # COPERTURA SOUND: QUALSIASI trap o budget-tempo sforato -> copertura INCOMPLETA -> NON certificabile (chiude il
    # trap-hide: un subject che trappa esattamente l'input 'cattivo' non puo' ottenere CONFIRMED). Solo 0 trap -> CONFIRMED.
    if traps > 0 or timed_out:
        return Verdict(Status.ABSTAIN, executed=True,
                       reason=f"copertura INCOMPLETA: {traps} input TRAPPANO"
                              + (" + budget-tempo sforato" if timed_out else "")
                              + " -> impossibile certificare (un subject che trappa l'input 'cattivo' NON e' un pass)",
                       coverage={"traps": traps, "trapped_sample": [str(t) for t in trapped[:10]],
                                 "timed_out": timed_out, "isolated": True, "checked": len(pairs)})
    if not pairs:
        return Verdict(Status.ABSTAIN, executed=True, reason="nessun input valutabile -> inconcludente",
                       coverage={"isolated": True})
    if exhaustive:
        return Verdict(Status.CONFIRMED, executed=True,
                       reason=f"WASM-isolato: proprieta' FIDATA '{prop}' vale su TUTTO il dominio dichiarato "
                              f"[{inputs[0]}..{inputs[-1]}] ({len(pairs)} valori, 0 trap) -> ESAUSTIVO",
                       witness={"checked": len(pairs), "domain": [inputs[0], inputs[-1]], "exhaustive": True},
                       reproduce=f"wasmtime zero-cap, fuel={fuel}, dominio esaustivo",
                       assurance=BOUNDED,   # sound ENTRO il dominio finito dichiarato (copertura completa, 0 trap)
                       coverage={"method": "WASM zero-cap esaustivo + oracolo host-fidato", "isolated": True,
                                 "exhaustive_domain": [inputs[0], inputs[-1]], "checked": len(pairs), "traps": 0},
                       assurance_caveat="BOUNDED: sound SOLO entro il dominio finito DICHIARATO (non oltre); copertura COMPLETA (0 trap).")
    resid = 3.0 / max(len(pairs), 1)
    return Verdict(Status.CONFIRMED, executed=True,
                   reason=f"WASM-isolato: proprieta' FIDATA '{prop}' regge su {len(pairs)} input (edge+campione, 0 trap) -> EMPIRICAL",
                   witness={"checked": len(pairs)}, reproduce=f"wasmtime zero-cap, fuel={fuel}, campione",
                   assurance=EMPIRICAL, residual_risk=resid,
                   coverage={"method": "WASM zero-cap campionato + oracolo host-fidato", "isolated": True, "checked": len(pairs), "traps": 0},
                   assurance_caveat="EMPIRICAL: campione (regola-del-3); per BOUNDED dichiara un dominio finito esaustivo.")


def claim_templates(target: str):
    return [Claim(domain="wasmprop", target=target, kind="trusted_property", params={"property": "nonnegative"})]


WASMPROP = Domain(name="wasmprop", gate=gate, claim_templates=claim_templates,
                  describe="Subject WASM zero-capability (isolato: frame-walk/host-escape impossibili PER COSTRUZIONE; "
                           "memoria+fuel+wall-clock cappati) + oracolo host-FIDATO. CONFIRMED solo con 0 TRAP (copertura "
                           "completa); un trap -> ABSTAIN -> REFUTED+controesempio | CONFIRMED(BOUNDED|EMPIRICAL) | ABSTAIN")
register(WASMPROP)
