"""verivault.cli — INTERFACCIA PRODOTTO.

Trasforma il kernel verification-native in un comando usabile da un cliente:

    verivault audit <source.sol> --key <shape>        # audita un sorgente -> certificato firmato
    verivault audit --onchain <address> --rpc <url>   # audita un vault DEPLOYATO (mainnet-fork)
    verivault demo                                     # esegue 2 audit reali (VULN + IMMUNE) e mostra i certificati

Output a 3 vie, ognuno con PROVA ESEGUIBILE ri-eseguibile:
  VULN     -> exploit eseguito dal forge-gate, con witness (profitto attaccante)
  IMMUNE   -> certificato che l'attacco NON è profittevole (witness: profitto <= 0)
  ABSTAIN  -> dichiarato (mai un finto-verdetto)

Self-contained: estrattore deterministico (niente API). Il forge-gate è l'adjudicatore sound.
"""
from __future__ import annotations
import argparse, json, os, sys

try:
    from . import audit_signed, audit_onchain, Status
    from . import certificate as _C
    from .autowire import autowire as _autowire
except ImportError:  # eseguito come script
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from verivault import audit_signed, audit_onchain, Status
    from verivault import certificate as _C
    from verivault.autowire import autowire as _autowire

_PKG = os.path.dirname(os.path.abspath(__file__))            # .../verivault/verivault
_REPO = os.path.dirname(_PKG)                                # .../verivault  (self-contained)
_STARTUP = os.path.dirname(_REPO)
_BUNDLED_GATE = os.path.join(_REPO, "gate")                 # .../verivault/gate  (forge-gate bundled)
_RESEARCH_GATE = os.path.join(_STARTUP, "research_substrate_capacity", "exp", "virgin", "gate")
DEFAULT_GATE = os.environ.get(
    "VERIVAULT_GATE", _BUNDLED_GATE if os.path.isdir(_BUNDLED_GATE) else _RESEARCH_GATE)

_LABEL = {"PASS": "PASS", "REFUTED": "REFUTED", "ABSTAIN": "ABSTAIN"}


def _verdict_human(cert_dict: dict) -> str:
    """Mappa il verdetto interno (PASS/REFUTED/ABSTAIN) nel linguaggio-prodotto VULN/IMMUNE/ABSTAIN."""
    v = cert_dict["verdict"]
    claim_kind = cert_dict.get("claim", {}).get("kind", "")
    st = v["status"]
    if st == "PASS" and "donation_inflation" in claim_kind:
        return "VULN (exploit ESEGUITO)"
    if st == "PASS":
        return "IMMUNE (prova eseguita: attacco non profittevole)"
    if st == "REFUTED":
        return "VULN (controesempio eseguito)"
    return "ABSTAIN (dichiarato)"


def _print_envelope(env: dict, title: str) -> None:
    cert = env["certificate"]
    v = cert["verdict"]
    print("\n" + "=" * 78)
    print(f"  CERTIFICATO VeriVault — {title}")
    print("=" * 78)
    print(f"  VERDETTO   : {_verdict_human(cert)}")
    print(f"  ragione    : {(v.get('reason') or '')[:120]}")
    if v.get("counterexample"):
        print(f"  WITNESS    : {str(v['counterexample'])[:120]}  (ri-eseguibile via forge)")
    if v.get("proof"):
        print(f"  prova      : {str(v['proof'])[:120]}")
    print(f"  script     : {v.get('script', '-')}")
    print(f"  content_hash: {env.get('content_hash', '')[:32]}...   (deterministico, contestabile)")
    print(f"  firma HMAC : {'presente' if env.get('hmac_sha256') else 'assente (passa --sign per firmare)'}")
    print("=" * 78)


def _to_envelope(cert, key):
    """Avvolge un Certificate (es. da audit_onchain) in una busta firmata portabile."""
    return _C.envelope(cert, key=key)


def cmd_audit(args) -> int:
    key = args.sign.encode() if args.sign else None
    if args.onchain:
        cert = audit_onchain(args.onchain, args.gate, args.onchain_test, args.key or "sdai", rpc_url=args.rpc)
        env = _to_envelope(cert, key)
        _print_envelope(env, f"on-chain {args.onchain[:10]}…")
    else:
        if not args.source:
            print("errore: fornisci <source.sol> oppure --onchain <address>", file=sys.stderr)
            return 2
        if args.key:
            env = audit_signed(args.source, args.gate, args.test, args.key, signing_key=key)
        else:
            # AUTO-WIRING (Stage-3 deterministico): genera l'harness fedele per QUALSIASI vault ERC-4626.
            try:
                ai = _autowire(args.source, args.gate)
            except Exception as e:  # noqa
                print(f"\n  ABSTAIN — auto-wiring non riuscito ({e}).")
                print("  Il vault potrebbe non essere ERC-4626/IVault-standard. Mai un finto-verdetto.")
                return 0
            print(f"  [autowire] harness fedele auto-generato per `{ai['contract']}` (deterministico, no-LLM)")
            _ANALYZABLE = {"totalAssets_type": "external_balanceOf", "defense_strength": 0.5,
                           "effective_offset_magnitude": 0.0, "dead_shares": False, "donation_vector": True}
            try:
                env = audit_signed(args.source, args.gate, ai["gate_test"], ai["result_key"],
                                   signing_key=key, llm_fact_fn=lambda s: dict(_ANALYZABLE))
            finally:
                ai["cleanup"]()
        _print_envelope(env, os.path.basename(args.source))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(env, f, indent=2, ensure_ascii=False, default=str)
        print(f"  [scritto] busta firmata -> {args.out}")
    return 0


def cmd_demo(args) -> int:
    """Esegue 2 audit REALI (un VULN + un IMMUNE) sul gate verificato: la demo consegnabile."""
    gate = args.gate
    targets = os.path.join(gate, "targets")
    cases = [
        ("VaultBalanceOf.sol", "solmate_balanceof", "atteso VULN (totalAssets=balanceOf, donazione manipolabile)"),
        ("OZVault.sol", "oz_offset0", "atteso IMMUNE (virtual-shares OZ)"),
    ]
    key = b"verivault-demo-key"
    n_ok = 0
    for fname, rk, note in cases:
        src = os.path.join(targets, fname)
        if not os.path.exists(src):
            print(f"  [skip] {fname} non trovato in {targets}")
            continue
        print(f"\n>>> audit {fname}  ({note})")
        try:
            env = audit_signed(src, gate, "test/GeneralGate.t.sol", rk, signing_key=key)
            _print_envelope(env, fname)
            if args.outdir:
                os.makedirs(args.outdir, exist_ok=True)
                p = os.path.join(args.outdir, fname.replace(".sol", "_cert.json"))
                json.dump(env, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False, default=str)
                print(f"  [scritto] {p}")
            n_ok += 1
        except Exception as e:  # noqa
            print(f"  [errore] {e}")
    print(f"\n  demo completata: {n_ok}/{len(cases)} certificati emessi (forge richiesto).")
    return 0 if n_ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="verivault",
        description="VeriVault — audit verification-native per ERC-4626: emette un CERTIFICATO con prova eseguibile "
                    "(VULN+exploit | IMMUNE+prova | ABSTAIN+ragione), mai un finto-verdetto.")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="audita un sorgente .sol o un indirizzo on-chain")
    a.add_argument("source", nargs="?", help="path al sorgente Solidity del vault")
    a.add_argument("--onchain", metavar="ADDR", help="audita un vault DEPLOYATO (richiede --rpc o ETH_RPC_URL)")
    a.add_argument("--rpc", help="URL RPC archive-node (o env ETH_RPC_URL) per il fork on-chain")
    a.add_argument("--key", help="shape/result_key (sorgente: es. solmate_balanceof, oz_offset0; on-chain: es. sdai)")
    a.add_argument("--gate", default=DEFAULT_GATE, help="dir del progetto forge-gate (default: env VERIVAULT_GATE)")
    a.add_argument("--test", default="test/GeneralGate.t.sol", help="path dell'harness sorgente")
    a.add_argument("--onchain-test", default="test/BenchGate.t.sol", help="path dell'harness on-chain")
    a.add_argument("--sign", metavar="SECRET", help="firma la busta con questa chiave HMAC (stringa)")
    a.add_argument("--out", help="scrivi la busta firmata (JSON) in questo file")
    a.set_defaults(func=cmd_audit)

    d = sub.add_parser("demo", help="esegue 2 audit reali (VULN + IMMUNE) e mostra i certificati")
    d.add_argument("--gate", default=DEFAULT_GATE, help="dir del progetto forge-gate")
    d.add_argument("--outdir", help="scrivi i certificati-demo in questa cartella")
    d.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
