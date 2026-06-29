"""_diff_runner — FUZZING DIFFERENZIALE TRANS-LINGUAGGIO in un subprocesso bounded (la Stele di Rosetta).

Carica il target (ref(x) in Python, gen(rng), IMPL_JS = sorgente di f(x) nell'altro linguaggio), genera N input
col SEED del kernel, esegue ref (Python) e l'impl (via `node`) sugli STESSI input, e confronta. Una DIVERGENZA
eseguita e' una PROVA di non-equivalenza (REFUTED + l'input esatto che diverge). Tutto il codice non-fidato gira
QUI, non nel kernel; il timeout del padre lo bounda.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile


def _num_eq(a, b):
    """Uguaglianza SEMANTICA robusta a int/float (2 == 2.0); ricorsiva su liste/dict; altro -> ==."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_num_eq(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_num_eq(a[k], b[k]) for k in a)
    return a == b


_JS_DRIVER = ("\nconst _ls=require('fs').readFileSync(0,'utf8').split('\\n').filter(s=>s.length);\n"
              "const _o=[];for(const _l of _ls){let _x=JSON.parse(_l);let _r;"
              "try{_r=f(_x);}catch(e){_r={__err__:String(e)};}"
              "_o.push(JSON.stringify(_r===undefined?null:_r));}\nprocess.stdout.write(_o.join('\\n'));\n")


def main():
    path, trials, seed, mem_mb, node = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
    contract = sys.argv[6] if len(sys.argv) > 6 else ""
    wall_s = float(sys.argv[7]) if len(sys.argv) > 7 else 10.0

    # CANALE-RISULTATO FIDATO (fix result-channel hijack): dup dello stdout reale prima del codice non-fidato.
    nonce = os.environ.get("SUBSTRATE_RJSON_NONCE", "")
    try:
        _real_out = os.dup(1)
    except Exception:
        _real_out = 1
    os.environ.pop("SUBSTRATE_RJSON_NONCE", None)

    def _emit(o):
        try:
            os.write(_real_out, ("RJSN" + nonce + json.dumps(o)).encode("utf-8", "replace"))
        except Exception:
            pass

    try:
        import resource
        lim = mem_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (lim, lim))
    except Exception:
        pass

    # ISOLAMENTO CANALE: il codice `ref` non-fidato gira qui -> stdout/stderr verso devnull.
    try:
        _devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(_devnull, 1)
        os.dup2(_devnull, 2)
    except Exception:
        pass

    out = {"status": "ABSTAIN", "reason": "runner non concluso"}
    hp = None
    try:
        spec = importlib.util.spec_from_file_location("diff_target", path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)   # codice non-fidato DENTRO il sandbox
        if any(not hasattr(m, n) for n in ("ref", "gen")) or not hasattr(m, "IMPL_JS"):
            out = {"status": "ABSTAIN", "reason": "il target deve definire ref(x), gen(rng), IMPL_JS"}
        else:
            import random
            rng = random.Random(seed)
            inputs = [m.gen(rng) for _ in range(trials)]
            if contract:
                try:
                    from substrate_core.contracts import check_contract
                    valid = [x for x in inputs if check_contract(x, contract)]
                    if not valid:
                        _emit({"status": "CONTRACT_VIOLATION", "contract": contract,
                               "reason": "gen() ha prodotto solo input FUORI-CONTRATTO (%s)" % contract})
                        return
                    inputs = valid
                except Exception:  # noqa
                    pass
            outs_ref = [m.ref(x) for x in inputs]                      # esecuzione 1: Python
            fd, hp = tempfile.mkstemp(suffix=".js", prefix="diffjs_")
            os.close(fd)
            with open(hp, "w", encoding="utf-8") as f:
                f.write(m.IMPL_JS + _JS_DRIVER)
            p = subprocess.run([node, hp], input="\n".join(json.dumps(x) for x in inputs),  # esecuzione 2: l'altro linguaggio
                               capture_output=True, text=True, timeout=wall_s)
            js_lines = [ln for ln in (p.stdout or "").split("\n") if ln != ""]
            if len(js_lines) != len(inputs):
                out = {"status": "ABSTAIN", "reason": "runtime impl: %d/%d output; stderr=%s"
                       % (len(js_lines), len(inputs), (p.stderr or "")[:140])}
            else:
                ref = None
                for i, (x, oref, jl) in enumerate(zip(inputs, outs_ref, js_lines)):
                    oimpl = json.loads(jl)
                    if not _num_eq(oref, oimpl):
                        ref = {"input": repr(x), "output_ref": repr(oref), "output_impl": repr(oimpl), "trial": i}
                        break
                out = ({"status": "REFUTED", "seed": seed, **ref} if ref is not None
                       else {"status": "CONFIRMED", "checked": len(inputs), "seed": seed})
    except subprocess.TimeoutExpired:
        out = {"status": "RESOURCE_EXCEEDED", "reason": "timeout %ss (impl non terminante?)" % wall_s}
    except MemoryError:
        out = {"status": "RESOURCE_EXCEEDED", "reason": "memoria esaurita (RLIMIT)"}
    except Exception as e:  # noqa
        out = {"status": "ABSTAIN", "reason": "esecuzione ha sollevato: %s: %s" % (type(e).__name__, e)}
    finally:
        if hp:
            try:
                os.remove(hp)
            except Exception:  # noqa
                pass

    _emit(out)


if __name__ == "__main__":
    main()
