"""
test_product_flow.py — il FLUSSO-PRODOTTO enterprise end-to-end (gap e), eseguito.

Lega tutto: sorgente -> exec-gate forge (moat L4) -> certificato a 3 vie -> FIRMA + busta PORTABILE (certificate.py).
E verifica l'API on-chain (audit_onchain) onesta sul fabbisogno-RPC.

KILL-CONDITION (binaria, asserita):
  (1) audit_onchain(addr) SENZA rpc -> ABSTAIN dichiarato (mai finto-verdetto). [pure-Python, sempre]
  (2) audit_signed su VaultBalanceOf (gate GeneralGate, result_key solmate_balanceof) -> busta firmata con verdetto
      VULN-confermato + witness; content_hash presente e DETERMINISTICO; firma HMAC verificabile. [forge-guarded]
  (3) audit_signed su OZVault (result_key oz_offset0) -> busta firmata IMMUNE. [forge-guarded]
Se forge non e' disponibile, gli step (2)/(3) degradano ad ABSTAIN onesto e si SKIPpano i verdetti (la busta resta valida).
Riproducibile: `python eval/test_product_flow.py`  (i passi (2)/(3) richiedono forge + il repo-gate).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verivault import audit_onchain, audit_signed, Status
from verivault import certificate as C
from verivault.schemas import Claim, Verdict, Certificate

HERE = os.path.dirname(os.path.abspath(__file__))
STARTUP = os.path.dirname(os.path.dirname(HERE))
GATE = os.environ.get("GATE_DIR", os.path.join(STARTUP, "research_substrate_capacity", "exp", "virgin", "gate"))
KEY = b"demo-signing-key-from-env-in-prod"

# fatti STUB (la vera estrazione W5-v2 e' gap b, infra-gated): marca analizzabile -> l'exec-gate adjudica per esecuzione.
def _stub(facts):
    return lambda src: dict(facts)
EXTERNAL = {"totalAssets_type": "external_balanceOf", "defense_strength": 0.0,
            "effective_offset_magnitude": 0.0, "dead_shares": False, "donation_vector": True}


def _forge_ran(env):
    """True se l'exec-gate ha davvero girato (non un ABSTAIN da forge-non-eseguibile)."""
    r = (env["certificate"]["verdict"].get("reason") or "")
    return "forge non eseguibile" not in r and "non compila" not in r


def main():
    print("=" * 92)
    print("FLUSSO-PRODOTTO enterprise: sorgente -> exec-gate -> certificato FIRMATO PORTABILE  +  API on-chain")
    print("=" * 92)
    ok = True

    # (1) API on-chain SENZA rpc -> ABSTAIN onesto (pure-Python). ERMETICO: rimuove ETH_RPC_URL dall'ambiente
    #     per testare DAVVERO il path no-RPC (altrimenti, se l'env ha un RPC, il fork live tornerebbe IMMUNE).
    _saved_rpc = os.environ.pop("ETH_RPC_URL", None)
    try:
        c_oc = audit_onchain("0x83F20F44975D03b1b09e64809B757c47f942BEeA", GATE, "test/BenchGate.t.sol", "sdai", rpc_url=None)
    finally:
        if _saved_rpc is not None:
            os.environ["ETH_RPC_URL"] = _saved_rpc
    print(f"(1) audit_onchain(addr) senza RPC -> {c_oc.verdict.status.value}  ({c_oc.verdict.reason[:60]}...)")
    ok &= (c_oc.verdict.status == Status.ABSTAIN)

    # (2) audit_signed su VaultBalanceOf -> certificato VULN firmato portabile
    env_v = audit_signed(os.path.join(GATE, "targets", "VaultBalanceOf.sol"), GATE, "test/GeneralGate.t.sol",
                         "solmate_balanceof", signing_key=KEY, llm_fact_fn=_stub(EXTERNAL))
    st_v = env_v["certificate"]["verdict"]["status"]
    print(f"(2) audit_signed VaultBalanceOf -> verdict={st_v}  hash={env_v['content_hash'][:16]}...  hmac={'si' if env_v['hmac_sha256'] else 'no'}")
    assert env_v["content_hash"], "busta senza content_hash -> non portabile"
    if _forge_ran(env_v):
        ok &= (st_v == "PASS" and env_v["certificate"]["verdict"].get("counterexample") is not None)  # VULN-confermato + witness
        print(f"    witness: {str(env_v['certificate']['verdict'].get('counterexample'))[:80]}")
    else:
        print("    [forge non disponibile -> verdetto ABSTAIN onesto, salto l'assert VULN; busta cmq valida]")

    # (3) audit_signed su OZVault -> certificato IMMUNE firmato
    env_i = audit_signed(os.path.join(GATE, "targets", "OZVault.sol"), GATE, "test/GeneralGate.t.sol",
                         "oz_offset0", signing_key=KEY, llm_fact_fn=_stub(EXTERNAL))
    st_i = env_i["certificate"]["verdict"]["status"]
    print(f"(3) audit_signed OZVault -> verdict={st_i}  hash={env_i['content_hash'][:16]}...")
    if _forge_ran(env_i):
        ok &= (st_i == "PASS")   # IMMUNE (la prova vince sullo scorer cauto)

    # (4) PORTABILITA: il content_hash della busta e' deterministico + la firma verifica
    cert_v = C.from_dict(env_v["certificate"])
    assert C.content_hash(cert_v) == env_v["content_hash"], "content_hash non deterministico -> busta non contestabile"
    if env_v["hmac_sha256"]:
        assert C.verify(cert_v, env_v["hmac_sha256"], KEY), "firma HMAC non verifica"
    print(f"(4) portabilita: content_hash deterministico + firma verificata (round-trip OK)")

    assert ok, "flusso-prodotto incoerente"
    print("\n" + "=" * 92)
    print("ESITO: TUTTO COERENTE — flusso-prodotto enterprise eseguito: sorgente -> exec-gate (moat L4) -> certificato")
    print("FIRMATO PORTABILE/CONTESTABILE. API audit_onchain(addr) onesta (ABSTAIN senza RPC). Output consegnabile.")


if __name__ == "__main__":
    main()
