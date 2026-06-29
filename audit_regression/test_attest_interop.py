"""Oracle for substrate -> in-toto/DSSE attestation interop (enterprise standards bridge).
KEY: a DSSE PAE known-answer (from the DSSE spec) proves spec-compliant signing -> cosign/in-toto-verify interop.
Plus: round-trip verify, body tamper -> fail, wrong issuer key -> fail."""
import os, sys, json, base64
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from substrate_core import attest, derive_pubkey, Claim, verify
KEY = b"verify-all-key"; PUB = derive_pubkey(KEY)
fails = []

# (1) DSSE PAE spec known-answer: proves the signed bytes match the DSSE standard exactly.
pae = attest._pae(b"http://example.com/HelloWorld", b"hello world")
if pae != b"DSSEv1 29 http://example.com/HelloWorld 11 hello world":
    fails.append(f"DSSE PAE not spec-compliant: {pae!r}")

# Build a real verdict (prefer the sound smt PROVEN; fall back to pyprop if z3 absent)
import substrate_core as sc
if "smt" in sc.REGISTRY:
    env = verify(Claim("smt", "x_plus_0", "forall_property",
                       {"property_smt2": "(declare-const x (_ BitVec 8))(assert (= (bvadd x #x00) x))"}), key=KEY)
else:
    env = verify(Claim("pyprop", os.path.join(REPO, "examples", "ex_abs.py"), "invariant", {"trials": 64}), key=KEY)

att = attest.to_attestation(env, key=KEY)
# (2) round-trip verify under the issuer pubkey
rep = attest.verify_attestation(att, pubkey=PUB)
if not rep["verified"]:
    fails.append("DSSE attestation did not verify under the issuer pubkey")
st = rep["statement"] or {}
if st.get("_type") != "https://in-toto.io/Statement/v1":
    fails.append(f"statement _type not in-toto v1: {st.get('_type')}")
if st.get("predicateType") != "https://substrate-core.dev/verdict/v0.1":
    fails.append("predicateType missing/wrong")
if (st.get("subject") or [{}])[0].get("digest", {}).get("sha256") != env["content_hash"]:
    fails.append("subject digest != cert content_hash")
if st.get("predicate", {}).get("status") != env["certificate"]["verdict"]["status"]:
    fails.append("predicate.status != verdict status")

# (3) body tamper -> verification fails (flip the predicate status in the payload)
tampered = dict(att)
body = json.loads(base64.standard_b64decode(att["payload"]))
body["predicate"]["status"] = "CONFIRMED" if body["predicate"]["status"] != "CONFIRMED" else "REFUTED"
tampered["payload"] = base64.standard_b64encode(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).decode()
if attest.verify_attestation(tampered, pubkey=PUB)["verified"]:
    fails.append("tampered attestation payload still verified (DSSE binding broken)")

# (4) wrong issuer key -> fails
if attest.verify_attestation(att, pubkey=derive_pubkey(b"attacker"))["verified"]:
    fails.append("attestation verified under a WRONG pubkey (no mint protection)")

# (5) red-team F1: DSSE spec says verifiers MUST accept URL-safe base64 too -> re-encode the SAME signed body url-safe
raw_body = base64.standard_b64decode(att["payload"])
url_att = dict(att); url_att["payload"] = base64.urlsafe_b64encode(raw_body).decode()
if not attest.verify_attestation(url_att, pubkey=PUB)["verified"]:
    fails.append("F1: URL-safe base64 payload (DSSE MUST-accept) was rejected (interop false-negative)")

# (6) red-team F2: whitespace-malleable payload must be REJECTED (envelope uniqueness for tlog/CID dedup)
ws_att = dict(att); ws_att["payload"] = att["payload"][:8] + "\n" + att["payload"][8:]
if attest.verify_attestation(ws_att, pubkey=PUB)["verified"]:
    fails.append("F2: whitespace-injected (non-canonical) base64 payload was accepted (malleable envelope)")

# (7) footgun: an UNVERIFIED envelope must NOT return a parsed statement (no trusting unverified content)
rep_bad = attest.verify_attestation({"payloadType": att["payloadType"], "payload": att["payload"], "signatures": []}, pubkey=PUB)
if rep_bad["verified"] or rep_bad["statement"] is not None:
    fails.append("footgun: unverified envelope returned a parsed statement")

# (8) F3: subject<->content_hash relationship surfaced (default subject_digest == content_hash)
if rep.get("subject_matches_content_hash") is not True:
    fails.append("F3: subject_matches_content_hash not surfaced/true for default subject_digest")

if fails:
    print("FAIL test_attest_interop:"); [print("  -", f) for f in fails]; sys.exit(1)
print("PASS test_attest_interop: DSSE PAE spec-compliant (known-answer) + in-toto v1 round-trip + tamper/wrong-key rejected")
