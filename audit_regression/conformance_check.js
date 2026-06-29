// conformance_check.js — VERIFICATORE TERZO (JS/Node) dei vettori golden SPEC v0.1.0.
// Prova EMPIRICAMENTE la determinismo cross-linguaggio: un'implementazione JS indipendente (Node crypto SHA-256 +
// tweetnacl Ed25519, gli STESSI primitivi del verificatore browser) DEVE riprodurre gli ESATTI content_hash di
// Python e verificare le firme. argv: <golden.json> <nacl.min.js path>. exit 0 = CONFORME.
const fs = require("fs");
const crypto = require("crypto");
const nacl = require(process.argv[3]);

function hex2bytes(h) { return Uint8Array.from(Buffer.from(h, "hex")); }

const vectors = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
let allOk = true;
for (const v of vectors) {
  // (1) sha256 dei BYTE CANONICI incastonati == content_hash (niente re-implementazione del JSON di Python)
  const h = crypto.createHash("sha256").update(Buffer.from(v.canonical, "utf8")).digest("hex");
  const hashOk = (h === v.content_hash);
  // (2) firma Ed25519 sul content_hash (gli stessi byte firmati dal kernel) verifica sotto la pubkey
  let sigOk = false;
  try {
    sigOk = nacl.sign.detached.verify(Buffer.from(v.content_hash, "utf8"), hex2bytes(v.sig), hex2bytes(v.pubkey));
  } catch (e) { sigOk = false; }
  if (!hashOk || !sigOk) allOk = false;
  console.log(`${v.name}: hash=${hashOk} sig=${sigOk}`);
}
console.log(allOk ? "CONFORMANT" : "NON-CONFORMANT");
process.exit(allOk ? 0 : 1);
