import sys
REPO = r"C:\Users\Utente\MODELLIPERSONALIZZATI\DC2026\Startup\substrate_core"
sys.path.insert(0, REPO)
from substrate_core import Claim, verify
from substrate_core.prover_seam import submit

KEY = b"verify-all-key"

print("=== (A) entity_probe crypto: fabricated cospend_inputs THROUGH THE SEAM ===")
# A prover that has NOT executed anything on-chain, just asserts two addresses are co-spent.
env = submit({"domain": "entity_probe", "target": "0xATTACKER",
              "kind": "entity_type:co_owned",
              "params": {"probe": "crypto", "a": "0xDEAD", "b": "0xBEEF",
                         "cospend_inputs": ["0xDEAD", "0xBEEF"], "tx": "0xfake",
                         # also try to assert the verdict directly:
                         "assurance": "proven", "status": "CONFIRMED"}}, key=KEY)
v = env["certificate"]["verdict"]
print("  stripped_assertions:", env["prover"]["stripped_assertions"])
print("  STATUS / ASSURANCE :", v["status"], "/", v["assurance"], " executed:", v["executed"])
print("  >>> seam-surviving false PROVEN" if (v["status"]=="CONFIRMED" and v["assurance"]=="proven")
      else "  >>> safe")

print("\n=== (B) replay: target ignored + fabricated witness via verify() ===")
for tgt in ("cream-attack", "totally-unknown-xyz-9999"):
    e = verify(Claim("replay", tgt, "replay_exploit",
                     {"input_witness": {"input": "(50, 100)"}, "profit": 999999999}), key=KEY)
    vv = e["certificate"]["verdict"]
    print(f"  target={tgt:26s} -> {vv['status']}/{vv['assurance']}  witness={vv.get('witness')}")

print("\n=== (C) replay: prover invents a profit out of thin air (no real attack) ===")
e = verify(Claim("replay", "anything", "replay_exploit",
                 {"input_witness": {"input": "(1, 1000000)"}}), key=KEY)
vv = e["certificate"]["verdict"]
print("  fabricated (D=1,V=1e6) ->", vv["status"], "/", vv["assurance"], " witness:", vv.get("witness"))
