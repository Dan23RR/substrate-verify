"""_wasi_host — lancia la valutazione pyprop DENTRO un guest python.wasm (wasm32-wasi) via wasmtime.

E' il RECINTO FISICO: il codice non-fidato (gen/subject/prop del prover + il driver) gira in un interprete CPython
compilato a WebAssembly, in una RAM virtuale separata. Conseguenze ARCHITETTURALI (provate dallo smoke-test):
  * sys._getframe nel guest vede SOLO i frame del guest -> NON puo' raggiungere il nonce/fd/kernel dell'HOST nativo
    (memoria diversa) -> FRAME-WALK-VERSO-IL-KERNEL neutralizzato;
  * WASI e' default-deny su filesystem/rete -> il guest non tocca l'host -> HOST-ESCAPE neutralizzato.
Questo modulo (TRUSTED) NON esegue codice non-fidato nativamente: lo confina nel guest e RILANCIA il risultato del
guest all'host, incorniciato col nonce (che il guest non puo' leggere: env WASI vuoto + isolamento di memoria).
RESIDUO ONESTO: il prover scrive ancora `prop` DENTRO il guest -> puo' falsare il PROPRIO report (oracle-control,
confinato al guest usa-e-getta). Percio' il tier resta EMPIRICAL; la novita' e' isolated=True (host/kernel blindati).

Invocato come subprocesso da sandbox.run_pyprop_wasi (che lo bounda col timeout = gas-meter wall-clock)."""
import json
import os
import sys
import tempfile

# Driver GUEST self-contained (nessun import substrate_core: il guest e' isolato). Stessa semantica del runner nativo:
# REFUTED+witness | CONFIRMED+harness(non-vacuita') | ABSTAIN. Scrive 'RJSON<json>' sullo stdout del GUEST.
_GUEST_DRIVER = r'''
import sys, json, random, os as _os, io as _io
sys.path.insert(0, "/s")
# HARDENING DEL CANALE (chiude il naive-hijack DENTRO il guest, complemento dell'isolamento WASI di memoria):
# il codice NON-FIDATO (import del target + subject/prop/gen) gira con os._exit NEUTRO e le write su fd 1/2
# DROPPATE -> non puo' forgiare un RJSON sul canale del runner, ovunque metta il forge (module-level o dentro subject).
# SOLO il driver scrive il risultato, via _rwrite (riferimento reale catturato prima del patch).
_rexit, _rwrite = _os._exit, _os.write
def _safe_write(fd, data):
    return len(data) if fd in (1, 2) else _rwrite(fd, data)
_os._exit = (lambda *a, **k: None)
_os.write = _safe_write
sys.stdout = _io.StringIO(); sys.stderr = _io.StringIO()
def _emit(o):
    try: _rwrite(1, ("RJSON" + json.dumps(o)).encode("utf-8", "replace"))
    except Exception: pass
try:
    import target as m
except Exception as _e:
    _emit({"status": "ABSTAIN", "reason": "import del target fallito: %s" % type(_e).__name__}); raise SystemExit

def _edges(sample):
    try:
        if isinstance(sample, bool): return [True, False]
        if isinstance(sample, int): return [0,1,-1,2,-2,1000,-1000,10**9,-(10**9),2**31-1,-(2**31)]
        if isinstance(sample, float): return [0.0,1.0,-1.0,0.5,-0.5,1e308,-1e308]
        if isinstance(sample, str): return ["","a","0"," ","\n","aa"]
        if isinstance(sample, (list,tuple)):
            el = sample[0] if sample else 0
            if isinstance(el, bool): base=[[],[True],[False,False]]
            elif isinstance(el,(int,float)): base=[[],[0],[-1],[0,0],[1,1,1],[-1,-2,-3],[10**9],[-(10**9),10**9],list(range(8))]
            elif isinstance(el,str): base=[[],[""],["a","a"],["b","a"]]
            else: base=[[],[el]]
            return [tuple(b) for b in base] if isinstance(sample,tuple) else base
    except Exception: return []
    return []

def _corrupt(y, r):
    try:
        if isinstance(y, bool): return [not y]
        if isinstance(y,(int,float)): return [y+r.uniform(1,1e6), -y-1.0, 0, 1e18]
        if isinstance(y, str): return [y[::-1]+"X","", y+"_C"]
        if isinstance(y,(list,tuple)):
            yl=list(y); c=[yl[::-1], yl[:-1], yl+[r.randint(-9,9)], []]
            return [tuple(x) for x in c] if isinstance(y,tuple) else c
        return [None,0,"CORRUPT"]
    except Exception: return [None,0]

def _vacuity(seed, n):
    r=random.Random(seed+7); rej=False
    for _ in range(min(max(n,1),200)):
        try: x=m.gen(r); y=m.subject(x)
        except Exception: continue
        for c in _corrupt(y, r):
            try:
                if not bool(m.prop(x,c)): rej=True; break
            except Exception: pass
        if rej: break
    return [] if rej else [{"mutant":"vacuity","note":"la prop non rifiuta mai un output corrotto"}]

trials=int(sys.argv[1]); seed=int(sys.argv[2]); edge=(len(sys.argv)>3 and sys.argv[3]=="1")
out={"status":"ABSTAIN","reason":"driver non concluso"}
try:
    miss=[n for n in ("subject","prop","gen") if not hasattr(m,n)]
    if miss:
        out={"status":"ABSTAIN","reason":"il target deve definire %s"%miss}
    else:
        rng=random.Random(seed); checked=0; ref=None
        for i in range(trials):
            x=m.gen(rng); y=m.subject(x); ok=bool(m.prop(x,y)); checked+=1
            if not ok: ref={"input":repr(x),"output":repr(y),"trial":i}; break
        if ref is None and edge:
            try: sample=m.gen(random.Random(seed+101))
            except Exception: sample=0
            for xe in _edges(sample):
                try: ye=m.subject(xe); oke=bool(m.prop(xe,ye))
                except Exception: continue
                checked+=1
                if not oke: ref={"input":repr(xe),"output":repr(ye),"trial":-1,"kernel_edge":True}; break
        if ref is not None:
            out={"status":"REFUTED","seed":seed, **ref}
        else:
            out={"status":"CONFIRMED","checked":checked,"seed":seed,"harness":{"survivors":_vacuity(seed,checked)}}
except Exception as e:
    out={"status":"ABSTAIN","reason":"esecuzione ha sollevato: %s: %s"%(type(e).__name__, e)}
_emit(out)
'''


def _run(target_path, trials, seed, edge_probe, wasm_path):
    import wasmtime
    with open(target_path, "r", encoding="utf-8") as f:
        target_src = f.read()
    d = tempfile.mkdtemp(prefix="wasi_s_")
    with open(os.path.join(d, "target.py"), "w", encoding="utf-8") as f:
        f.write(target_src)
    with open(os.path.join(d, "driver.py"), "w", encoding="utf-8") as f:
        f.write(_GUEST_DRIVER)
    out_f = os.path.join(d, "guest_stdout.txt")
    eng = wasmtime.Engine()
    linker = wasmtime.Linker(eng)
    linker.define_wasi()
    module = wasmtime.Module.from_file(eng, wasm_path)
    store = wasmtime.Store(eng)
    w = wasmtime.WasiConfig()
    w.argv = ["python", "/s/driver.py", str(int(trials)), str(int(seed)), "1" if edge_probe else "0"]
    # RECINTO: SOLO la dir dello script, READ-ONLY; nessun'altra dir, nessuna rete, env VUOTO (no nonce host nel guest).
    try:
        w.preopen_dir(d, "/s", wasmtime.DirPerms.READ, wasmtime.FilePerms.READ)
    except Exception:
        w.preopen_dir(d, "/s")   # fallback per API piu' vecchie
    w.stdout_file = out_f
    w.stderr_file = os.path.join(d, "guest_stderr.txt")
    store.set_wasi(w)
    inst = linker.instantiate(store, module)
    try:
        inst.exports(store)["_start"](store)
    except Exception:
        pass   # ExitTrap su sys.exit(0) / trap del guest
    txt = ""
    try:
        with open(out_f, "r", encoding="utf-8", errors="replace") as f:
            txt = f.read()
    except Exception:
        pass
    idx = txt.find("RJSON")
    if idx < 0:
        return {"status": "RESOURCE_EXCEEDED", "reason": "il guest WASI non ha prodotto risultato (trap/startup?)"}
    try:
        return json.loads(txt[idx + len("RJSON"):])
    except Exception:
        return {"status": "ABSTAIN", "reason": "output del guest WASI non parsabile"}


def main():
    target_path, trials, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    edge_probe = (len(sys.argv) > 4 and sys.argv[4] == "1")
    wasm_path = sys.argv[5]
    nonce = os.environ.get("SUBSTRATE_RJSON_NONCE", "")
    try:
        _real = os.dup(1)
    except Exception:
        _real = 1
    os.environ.pop("SUBSTRATE_RJSON_NONCE", None)
    try:
        out = _run(target_path, trials, seed, edge_probe, wasm_path)
    except Exception as e:  # noqa  (wasmtime non avviabile / .wasm assente, ecc.)
        out = {"status": "ABSTAIN", "reason": "wasi-host non avviabile: %s: %s" % (type(e).__name__, e)}
    out["isolated"] = True   # eseguito nel recinto WASM: host/kernel non raggiungibili
    try:
        os.write(_real, ("RJSN" + nonce + json.dumps(out)).encode("utf-8", "replace"))
    except Exception:
        pass


if __name__ == "__main__":
    main()
