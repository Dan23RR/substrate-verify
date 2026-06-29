"""substrate_core.cli — INTERFACCIA dell'infrastruttura verification-native.

    substrate verify <target> --domain <d>     # adjudica un claim -> certificato firmato a 3 vie
    substrate sweep  <targets...> --domain <d>  # organismo autonomo: naviga + compone in sistema
    substrate demo                              # 2 domini (Python + Solidity) sotto UN kernel
    substrate domains                           # elenca i domini registrati

Esito a 3 vie, ognuno con PROVA ESEGUITA ri-eseguibile:
  REFUTED   -> controesempio eseguito (claim FALSO) + witness
  CONFIRMED -> evidenza eseguita che il claim regge + witness
  ABSTAIN   -> dichiarato, ragione tipata (mai un finto-verdetto)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

try:
    from . import REGISTRY, Claim, verify, get_domain
    from .organism import navigate, sweep
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from substrate_core import REGISTRY, Claim, verify, get_domain
    from substrate_core.organism import navigate, sweep

def _render(v: dict) -> str:
    """Rendering ONESTO del lattice di assurance: nessun tier puo' apparire piu' forte di quanto e'."""
    st = v.get("status"); a = v.get("assurance", "none")
    cov = v.get("coverage", {}) or {}
    if st == "REFUTED":
        return "[X] REFUTED  (prova: controesempio eseguito)" if a == "proven" else "[X] REFUTED"
    if st == "CONFIRMED":
        if a == "proven":
            return "[v] PROVEN  (sound: esaustivo / controesempio eseguito)"
        if a == "proven-spec":
            return f"[v] PROVEN-SPEC  (simbolico UNSAT entro k={cov.get('bound_k', '?')})"
        if a == "bounded":
            return "[=] NON-REFUTATO  (bounded: esaustivo su spazio definito - NON generale)"
        rr = v.get("residual_risk")
        det = f"{cov.get('trials')} trial" if cov.get("trials") else cov.get("method", "campionato")
        rr_s = f", rischio-residuo<={rr:.4g}" if isinstance(rr, (int, float)) else ""
        return f"[~] NON-REFUTATO  (empirico: {det}{rr_s} - NON una prova)"
    return "[-] ABSTAIN"


def _print_cert(env: dict, title: str = "") -> None:
    cert = env["certificate"]
    v = cert["verdict"]
    print("\n" + "=" * 76)
    print(f"  CERTIFICATO substrate_core - {title or cert['claim']['target']}")
    print("=" * 76)
    print(f"  dominio    : {cert['claim']['domain']}   claim: {cert['claim']['kind']}")
    print(f"  VERDETTO   : {_render(v)}   (eseguito={v['executed']})")
    print(f"  assurance  : {v.get('assurance', 'none')}   coverage: {str(v.get('coverage', {}))[:72]}")
    if v.get("residual_risk") is not None:
        print(f"  rischio-res: <= {v['residual_risk']:.4g}   [{(v.get('assurance_caveat') or '')[:80]}]")
    print(f"  ragione    : {(v.get('reason') or '')[:108]}")
    if v.get("witness"):
        print(f"  witness    : {str(v['witness'])[:108]}  (ri-eseguibile)")
    print(f"  content_hash: {env.get('content_hash', '')[:32]}...   firma: {'si (ed25519)' if env.get('sig') else 'no'}")
    print("=" * 76)


def _params_from_args(args) -> dict:
    p = {}
    if getattr(args, "result_key", None):
        p["result_key"] = args.result_key
    if getattr(args, "gate", None):
        p["gate"] = args.gate
    if getattr(args, "test", None):
        p["test"] = args.test
    if getattr(args, "trials", None):
        p["trials"] = args.trials
    return p


def cmd_verify(args) -> int:
    key = args.sign.encode() if args.sign else None
    claim = Claim(domain=args.domain, target=args.target, kind=args.kind or "default", params=_params_from_args(args))
    env = verify(claim, key=key, stamp=args.stamp or "")
    _print_cert(env, os.path.basename(args.target))
    if args.out:
        json.dump(env, open(args.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False, default=str)
        print(f"  [scritto] {args.out}")
    return 0


def cmd_sweep(args) -> int:
    key = args.sign.encode() if args.sign else None
    items = [(t, args.domain, _params_from_args(args)) for t in args.targets]
    res = sweep(items, key=key, stamp=args.stamp or "")
    for r in res["items"]:
        for env in r["certificates"]:
            _print_cert(env, os.path.basename(r["target"]))
    sysv = res["system"]["certificate"]["verdict"] if res["system"] else None
    print("\n" + "#" * 76)
    print(f"  SISTEMA (composizione AND di {res['n_certs']} certificati): "
          f"{_render(sysv) if sysv else '-'}")
    if sysv:
        print(f"  {sysv['reason']}")
    print("#" * 76)
    if args.out:
        json.dump(res["system"], open(args.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False, default=str)
        print(f"  [scritto sistema] {args.out}")
    return 0


def cmd_demo(args) -> int:
    """Mostra UN kernel su DUE domini: Python-property (sempre) + Solidity/ERC-4626 (se forge)."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ex = os.path.join(here, "examples")
    key = b"substrate-demo-key"
    print(">>> DOMINIO 1: pyprop (proprieta' eseguibili su Python) — self-contained")
    for f, note in [("ex_abs.py", "atteso CONFIRMED"), ("ex_buggy_sort.py", "atteso REFUTED+witness")]:
        env = verify(Claim("pyprop", os.path.join(ex, f), "invariant", {"trials": 500, "seed": 0}), key=key)
        _print_cert(env, f"{f}  ({note})")
    if "erc4626" in REGISTRY:
        print("\n>>> DOMINIO 2: erc4626 (exec-gate forge Solidity) — STESSO kernel")
        try:
            import verivault
            g = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(verivault.__file__))), "gate")
            tg = os.path.join(g, "targets")
            for f, rk, note in [("VaultBalanceOf.sol", "solmate_balanceof", "atteso REFUTED/VULN"),
                                ("OZVault.sol", "oz_offset0", "atteso CONFIRMED/IMMUNE")]:
                env = verify(Claim("erc4626", os.path.join(tg, f), "immunity:donation_inflation",
                                   {"gate": g, "result_key": rk, "test": "test/GeneralGate.t.sol"}), key=key)
                _print_cert(env, f"{f}  ({note})")
        except Exception as e:  # noqa
            print(f"  [erc4626 saltato: {e}]")
    else:
        print("\n>>> DOMINIO 2 erc4626 non disponibile (verivault/forge assenti) — il kernel vive comunque.")
    print("\nUN kernel verification-native, domini eterogenei, stesso certificato firmato/componibile.")
    return 0


def cmd_domains(args) -> int:
    print("Domini registrati nel kernel substrate_core:")
    for name in sorted(REGISTRY):
        print(f"  - {name:10s} : {REGISTRY[name].describe}")
    return 0


def cmd_conformance(args) -> int:
    """Esegue la suite di vettori GOLDEN dello SPEC: un verificatore terzo DEVE riprodurli (cross-impl)."""
    from .conformance import check_conformance, PUBKEY
    rep = check_conformance()
    print(f"SPEC v0.1.0 conformance (emittente {PUBKEY[:16]}...):")
    for r in rep["vectors"]:
        print(f"  {r['name']:22s} hash={'ok ' if r['hash_ok'] else 'BAD'} sig={'ok ' if r['sig_ok'] else 'BAD'}  {r['content_hash'][:28]}...")
    print("CONFORMANT" if rep["conformant"] else "NON-CONFORMANT")
    return 0 if rep["conformant"] else 1


def cmd_prove_smt(args) -> int:
    """Tier FORMALE da CLI: prova una proprieta' SMT-LIB2 (oracolo Z3) -> PROVEN(UNSAT) | REFUTED(model) | ABSTAIN."""
    if "smt" not in REGISTRY:
        print("dominio 'smt' non disponibile (z3 assente: pip install z3-solver)")
        return 2
    smt2 = open(args.file, encoding="utf-8").read()
    key = args.sign.encode() if args.sign else None
    env = verify(Claim("smt", os.path.basename(args.file), "forall_property", {"property_smt2": smt2}), key=key)
    _print_cert(env, os.path.basename(args.file))
    if args.out:
        json.dump(env, open(args.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False, default=str)
        print(f"  [scritto] {args.out}")
    return 0


def cmd_attest(args) -> int:
    """Emette un certificato come attestazione in-toto v1 in busta DSSE (interop cosign/Sigstore/policy-controller)."""
    from .attest import to_attestation, verify_attestation
    from . import derive_pubkey
    key = args.sign.encode() if args.sign else None
    if not key:
        print("--sign SEED richiesto per firmare l'attestazione")
        return 2
    env = json.load(open(args.cert, encoding="utf-8"))
    dsse = to_attestation(env, key=key)
    ok = verify_attestation(dsse, pubkey=derive_pubkey(key))["verified"]
    out = args.out or (args.cert + ".dsse.json")
    json.dump(dsse, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"attestazione in-toto/DSSE (predicateType https://substrate-core.dev/verdict/v0.1) verify={'ok' if ok else 'BAD'}")
    print(f"  [scritto] {out}")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="substrate",
                                description="substrate_core — infrastruttura verification-native domain-agnostic.")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify", help="adjudica un claim su un target")
    v.add_argument("target")
    v.add_argument("--domain", required=True)
    v.add_argument("--kind", default=None)
    v.add_argument("--result-key", dest="result_key", default=None)
    v.add_argument("--gate", default=None)
    v.add_argument("--test", default=None)
    v.add_argument("--trials", type=int, default=None)
    v.add_argument("--sign", default=None)
    v.add_argument("--stamp", default=None)
    v.add_argument("--out", default=None)
    v.set_defaults(func=cmd_verify)

    s = sub.add_parser("sweep", help="organismo autonomo: naviga piu' target e componi in sistema")
    s.add_argument("targets", nargs="+")
    s.add_argument("--domain", required=True)
    s.add_argument("--result-key", dest="result_key", default=None)
    s.add_argument("--gate", default=None)
    s.add_argument("--test", default=None)
    s.add_argument("--trials", type=int, default=None)
    s.add_argument("--sign", default=None)
    s.add_argument("--stamp", default=None)
    s.add_argument("--out", default=None)
    s.set_defaults(func=cmd_sweep)

    d = sub.add_parser("demo", help="UN kernel su due domini (Python + Solidity)")
    d.set_defaults(func=cmd_demo)

    dl = sub.add_parser("domains", help="elenca i domini registrati")
    dl.set_defaults(func=cmd_domains)

    cf = sub.add_parser("conformance", help="esegue i vettori GOLDEN dello SPEC (cross-impl)")
    cf.set_defaults(func=cmd_conformance)

    ps = sub.add_parser("prove-smt", help="tier FORMALE: prova una proprieta' SMT-LIB2 (oracolo Z3)")
    ps.add_argument("file")
    ps.add_argument("--sign", default=None)
    ps.add_argument("--out", default=None)
    ps.set_defaults(func=cmd_prove_smt)

    at = sub.add_parser("attest", help="emette un certificato come attestazione in-toto/DSSE")
    at.add_argument("cert", help="file JSON della busta-certificato")
    at.add_argument("--sign", required=True)
    at.add_argument("--out", default=None)
    at.set_defaults(func=cmd_attest)
    return p


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # robusto su console non-UTF8
    except Exception:  # noqa
        pass
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
