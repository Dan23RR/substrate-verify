"""_pyprop_runner — esegue la valutazione pyprop in un SUBPROCESSO ISOLATO (il 'gas meter').

Invocato da sandbox.py. Tutto il codice NON-FIDATO (import del target, fuzz, meta-verifica harness, co-fuzzer
kernel) gira QUI, non nel kernel. Limita la MEMORIA (RLIMIT su POSIX) e — via il timeout del padre — il TEMPO.
Stampa il risultato come 'RJSON<json>' su stdout. Un while-True/memory-bomb fa morire QUESTO figlio, mai il kernel.
"""
import importlib.util
import json
import os
import random
import sys


def _edge_inputs(sample):
    """Input avversariali KERNEL-scelti per il TIPO inferito da un campione di gen() (CO-FUZZER). Chiude
    l'evasione-COMUNE di distribuzione: un gen() che evita una sotto-regione del proprio tipo (es. solo positivi
    mentre il bug e' sui negativi). NON trova un bug nascosto in un punto singolo arbitrario: limite irriducibile
    del fuzzing black-box -> per questo il tier resta EMPIRICAL e il caveat segnala la dipendenza da gen()."""
    try:
        if isinstance(sample, bool):
            return [True, False]
        if isinstance(sample, int):
            return [0, 1, -1, 2, -2, 1000, -1000, 10**9, -(10**9), 2**31 - 1, -(2**31)]
        if isinstance(sample, float):
            return [0.0, 1.0, -1.0, 0.5, -0.5, 1e308, -1e308]
        if isinstance(sample, str):
            return ["", "a", "0", " ", "\n", "aa"]
        if isinstance(sample, (list, tuple)):
            el = sample[0] if sample else 0
            if isinstance(el, bool):
                base = [[], [True], [False, False]]
            elif isinstance(el, (int, float)):
                base = [[], [0], [-1], [0, 0], [1, 1, 1], [-1, -2, -3], [10**9], [-(10**9), 10**9], list(range(8))]
            elif isinstance(el, str):
                base = [[], [""], ["a", "a"], ["b", "a"]]
            else:
                base = [[], [el]]
            return [tuple(b) for b in base] if isinstance(sample, tuple) else base
    except Exception:  # noqa
        return []
    return []


def main():
    path, trials, seed, mem_mb = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    edge_probe = (len(sys.argv) > 5 and sys.argv[5] == "1")
    contract = sys.argv[6] if len(sys.argv) > 6 else ""

    # CANALE-RISULTATO FIDATO (fix result-channel hijack): duplica lo stdout reale PRIMA di eseguire codice
    # non-fidato, poi rimuovi il nonce dall'ambiente. Il verdetto del runner uscira' SOLO su _real_out,
    # incorniciato col nonce scelto dal kernel; cio' che il codice non-fidato scrive su 1/2 finira' nel vuoto.
    nonce = os.environ.get("SUBSTRATE_RJSON_NONCE", "")
    try:
        _real_out = os.dup(1)
    except Exception:
        _real_out = 1
    os.environ.pop("SUBSTRATE_RJSON_NONCE", None)

    try:  # cap di memoria (POSIX); su Windows il timeout del padre + isolamento-processo coprono il vettore
        import resource
        lim = mem_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (lim, lim))
    except Exception:
        pass

    # CONTRACT-GATE: validatore di tipo (importato SOLO se un contratto e' dichiarato -> zero costo altrove)
    _check = None
    if contract:
        try:
            from substrate_core.contracts import check_contract as _check
        except Exception:  # noqa
            _check = None

    # ISOLAMENTO DEL CANALE: da qui in poi gira codice NON-FIDATO -> stdout/stderr verso devnull. Un harness
    # che fa `print("RJSON{...CONFIRMED}")` (anche seguito da os._exit) scrive nel vuoto, non sul canale del kernel.
    try:
        _devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(_devnull, 1)
        os.dup2(_devnull, 2)
    except Exception:
        pass

    out = {"status": "ABSTAIN", "reason": "runner non concluso"}
    try:
        spec = importlib.util.spec_from_file_location("subject_under_test", path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)   # <- import del target (codice non-fidato) DENTRO il sandbox
        missing = [n for n in ("subject", "prop", "gen") if not hasattr(m, n)]
        if missing:
            out = {"status": "ABSTAIN", "reason": f"il target deve definire {missing} (subject, prop, gen)"}
        else:
            rng = random.Random(seed)
            checked = 0
            invalid = 0
            ref = None
            for i in range(trials):
                x = m.gen(rng)
                if _check is not None and not _check(x, contract):
                    invalid += 1
                    if checked == 0 and invalid >= 16:   # gen() produce SOLO garbage -> fuori-contratto, stop
                        break
                    continue                              # input fuori-contratto: NON e' un controesempio lecito
                y = m.subject(x); ok = bool(m.prop(x, y)); checked += 1
                if not ok:
                    ref = {"input": repr(x), "output": repr(y), "trial": i}
                    break
            if ref is None and _check is not None and checked == 0 and invalid > 0:
                # Il prover non ha prodotto NEMMENO UN input valido -> rigetto al contract-gate, niente fuzz sprecato.
                out = {"status": "CONTRACT_VIOLATION", "invalid": invalid, "contract": contract,
                       "reason": f"gen() ha prodotto solo input FUORI-CONTRATTO ({contract}) su {invalid} campioni"}
            else:
                if ref is None and edge_probe:
                    # CO-FUZZER KERNEL: input-edge della stessa FORMA di gen() -> il prover non sceglie da solo la
                    # distribuzione di test. Chiude l'evasione di sotto-regione; non il punto-singolo nascosto.
                    try:
                        sample = m.gen(random.Random(seed + 101))
                    except Exception:  # noqa
                        sample = 0
                    for xe in _edge_inputs(sample):
                        if _check is not None and not _check(xe, contract):
                            continue   # edge fuori-contratto: non e' un controesempio lecito
                        try:
                            ye = m.subject(xe); oke = bool(m.prop(xe, ye))
                        except Exception:  # noqa
                            continue   # un'eccezione su un edge non e' una refutazione (inconclusivo)
                        checked += 1
                        if not oke:
                            ref = {"input": repr(xe), "output": repr(ye), "trial": -1, "kernel_edge": True}
                            break
                if ref is not None:
                    out = {"status": "REFUTED", "seed": seed, **ref}
                else:
                    from substrate_core.harness import score_pyprop_harness
                    out = {"status": "CONFIRMED", "checked": checked, "seed": seed,
                           "harness": score_pyprop_harness(m, seed, checked)}
    except MemoryError:
        out = {"status": "RESOURCE_EXCEEDED", "reason": "memoria esaurita (RLIMIT)"}
    except Exception as e:  # noqa
        out = {"status": "ABSTAIN", "reason": f"esecuzione ha sollevato: {type(e).__name__}: {e}"}

    # Verdetto FIDATO sul canale duplicato, incorniciato col nonce del kernel (raw os.write: bypassa il devnull).
    try:
        os.write(_real_out, ("RJSN" + nonce + json.dumps(out)).encode("utf-8", "replace"))
    except Exception:
        pass


if __name__ == "__main__":
    main()
