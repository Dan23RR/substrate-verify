"""Oracle for the content-addressed overlay slice (substrate_core.cid): IPFS-compatible CIDv1 addressing of .scar/code.
Known-answer test against the canonical IPFS empty-block CIDv1 proves real interoperability (not a bespoke hash)."""
import os, sys, hashlib
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from substrate_core.cid import scar_cid, decode_cid, verify_cid

fails = []
# (1) KNOWN-ANSWER: matches `ipfs add --raw-leaves --cid-version=1` of empty content -> real IPFS compatibility.
EMPTY_CID = "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"
if scar_cid(b"") != EMPTY_CID:
    fails.append(f"empty CIDv1 mismatch (not IPFS-compatible): {scar_cid(b'')}")
# (2) deterministic + collision-distinct
if scar_cid(b"running_max") != scar_cid(b"running_max"):
    fails.append("scar_cid not deterministic")
if scar_cid(b"running_max") == scar_cid(b"running_min"):
    fails.append("distinct content collided")
# (3) structure is spec-conformant CIDv1/raw/sha2-256 and the digest is the real sha256
d = decode_cid(scar_cid(b"hello scar"))
if not (d["version"] == 1 and d["codec"] == 0x55 and d["mh_code"] == 0x12 and d["mh_len"] == 32):
    fails.append(f"CID structure non-conformant: {d}")
if d["digest"] != hashlib.sha256(b"hello scar").hexdigest():
    fails.append("CID digest != sha256(content)")
# (4) zero-trust verify: matches the right content, rejects tampered content / tampered CID
c = scar_cid(b"the-scar-bytes")
if not verify_cid(c, b"the-scar-bytes"):
    fails.append("verify_cid rejected the correct content")
if verify_cid(c, b"the-scar-bytes-TAMPERED"):
    fails.append("verify_cid accepted tampered content")
if verify_cid(c[:-1] + ("a" if c[-1] != "a" else "b"), b"the-scar-bytes"):
    fails.append("verify_cid accepted a CID that doesn't match its own content")

if fails:
    print("FAIL test_cid_overlay:"); [print("  -", f) for f in fails]; sys.exit(1)
print("PASS test_cid_overlay: IPFS-compatible CIDv1 (known-answer) + deterministic + zero-trust verify (content-addressed Lens slice)")
