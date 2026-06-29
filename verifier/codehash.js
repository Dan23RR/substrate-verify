// codehash.js — il GEMELLO JS di substrate_core.github_adapter.code_hash (stessa normalizzazione -> stesso hash).
// Normalizzazione CANONICA: CRLF->LF, rstrip per riga (solo spazi/tab), trim dei soli newline ai bordi.
// SHA-256 (WebCrypto) del testo normalizzato = identificatore STABILE del codice, identico lato Python.
function normalizeCode(src) {
  const s = String(src == null ? "" : src).replace(/\r\n?/g, "\n");
  const lines = s.split("\n").map(l => l.replace(/[ \t]+$/g, ""));  // rstrip(" \t") per riga
  return lines.join("\n").replace(/^\n+|\n+$/g, "");                  // strip("\n") ai bordi
}
async function codeHash(src) {
  const data = new TextEncoder().encode(normalizeCode(src));
  const d = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(d)).map(x => x.toString(16).padStart(2, "0")).join("");
}
if (typeof window !== "undefined") { window.normalizeCode = normalizeCode; window.codeHash = codeHash; }
