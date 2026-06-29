// worker_core.js — LA LIBRERIA DEL SERVICE-WORKER (isolata dal main thread e dalla CSP della pagina).
// Contiene: code_hash canonico, estrazione ROBUSTA di funzioni (gemello di codeextract.py), crypto del .scar
// (gunzip + SHA-256 + Ed25519). Gira in background.js (estensione reale) e, via chrome_shim.js, nella demo.
// Il content-script resta "stupido": legge il DOM, manda qui i dati, riceve DOVE iniettare.

// ---- code_hash canonico (gemello di github_adapter.code_hash) -------------------------------------------------
function normalizeCode(src) {
  const s = String(src == null ? "" : src).replace(/\r\n?/g, "\n");
  return s.split("\n").map(l => l.replace(/[ \t]+$/g, "")).join("\n").replace(/^\n+|\n+$/g, "");
}
async function codeHash(src) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(normalizeCode(src)));
  return Array.from(new Uint8Array(d)).map(x => x.toString(16).padStart(2, "0")).join("");
}

// ---- estrazione ROBUSTA di funzioni dal sorgente COMPLETO (gemello di codeextract.extract_functions) ----------
function _scanStrings(lines) {
  const res = []; let inStr = null;
  for (const ln of lines) {
    res.push(inStr !== null);
    let idx = 0;
    while (true) {
      const t1 = ln.indexOf("'''", idx), t2 = ln.indexOf('"""', idx);
      const cands = [];
      if (t1 >= 0) cands.push([t1, "'''"]);
      if (t2 >= 0) cands.push([t2, '"""']);
      if (!cands.length) break;
      cands.sort((a, b) => a[0] - b[0]);
      const pos = cands[0][0], delim = cands[0][1];
      if (inStr === null) inStr = delim; else if (inStr === delim) inStr = null;
      idx = pos + 3;
    }
  }
  return res;
}
function extractFunctions(source) {
  const s = String(source == null ? "" : source).replace(/\r\n?/g, "\n");
  const lines = s.split("\n");
  const sstr = _scanStrings(lines);
  const out = []; let i = 0; const n = lines.length;
  while (i < n) {
    const ln = lines[i];
    const st = ln.replace(/^[ \t]*/, "");
    if (!sstr[i] && (st.startsWith("def ") || st.startsWith("async def "))) {
      const indent = ln.length - st.length;
      const name = st.split("(")[0].replace("async def", "").replace("def", "").trim();
      let j = i + 1;
      while (j < n) {
        const lj = lines[j];
        if (lj.trim() === "" || sstr[j]) { j++; continue; }
        if (lj.length - lj.replace(/^[ \t]*/, "").length <= indent) break;
        j++;
      }
      let end = j;
      while (end - 1 > i && lines[end - 1].trim() === "") end--;
      out.push({ name: name, start: i, end: end, src: lines.slice(i, end).join("\n") });
      i = j;
    } else i++;
  }
  return out;
}

// ---- crypto del .scar (gemello del Pilastro 3) ----------------------------------------------------------------
const _enc = new TextEncoder();
const _hexToBytes = h => { const a = new Uint8Array(h.length / 2); for (let i = 0; i < a.length; i++) a[i] = parseInt(h.substr(i * 2, 2), 16); return a; };
const _bytesToHex = b => Array.from(b).map(x => x.toString(16).padStart(2, "0")).join("");
async function _sha256Hex(bytes) { return _bytesToHex(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))); }
async function _gunzip(buf) {
  if (typeof DecompressionStream === "undefined") throw new Error("DecompressionStream non supportato");
  return await new Response(new Blob([buf]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
}
function _deepEqual(a, b) {
  if (a === b) return true;
  if (typeof a !== typeof b || a === null || b === null) return a === b;
  if (Array.isArray(a)) { if (!Array.isArray(b) || a.length !== b.length) return false; for (let i = 0; i < a.length; i++) if (!_deepEqual(a[i], b[i])) return false; return true; }
  if (typeof a === "object") { const ka = Object.keys(a), kb = Object.keys(b); if (ka.length !== kb.length) return false; for (const k of ka) if (!_deepEqual(a[k], b[k])) return false; return true; }
  return false;
}
const _stripStamp = c => { const o = {}; for (const k of Object.keys(c)) if (k !== "stamp") o[k] = c[k]; return o; };
async function verifyScarBuf(buf) {
  const bundle = JSON.parse(await _gunzip(buf));
  const issuerPub = bundle.pubkey || null;
  const certs = bundle.certs || {};
  let allOk = true, nH = 0, nS = 0, nB = 0, n = 0; const refuted = [];
  for (const [ch, env] of Object.entries(certs)) {
    n++;
    let hashOk = false, bindOk = false, sigOk = false;
    try {
      if (typeof env.canonical === "string") {
        hashOk = (await _sha256Hex(_enc.encode(env.canonical))) === env.content_hash;
        bindOk = _deepEqual(JSON.parse(env.canonical), _stripStamp(env.certificate));
      }
      const pub = issuerPub || env.pubkey;
      if (env.sig && pub && typeof nacl !== "undefined")
        sigOk = nacl.sign.detached.verify(_enc.encode(env.content_hash), _hexToBytes(env.sig), _hexToBytes(pub));
    } catch (e) { /* resta false */ }
    if (hashOk) nH++; if (sigOk) nS++; if (bindOk) nB++;
    allOk = allOk && hashOk && bindOk && sigOk;
    const v = env.certificate.verdict;
    if (v.status === "REFUTED") { const w = v.witness || {}; refuted.push({ input: w.input, output: w.output, content_hash: ch }); }
  }
  return { ok: allOk && n > 0, n, refuted, pubkey: issuerPub, checks: `${nH}/${n} SHA-256 · ${nS}/${n} Ed25519 · ${nB}/${n} binding` };
}

// ---- HANDLER (indipendenti dal trasporto: background.js e chiamano questi iniettando fetch) -------------------
// getIndex(): -> oggetto indice ;  getRaw(file): -> sorgente COMPLETO (raw al commit) o "" ;  getBuf(url): -> ArrayBuffer
async function handleScan(payload, getIndex, getRaw) {
  const index = await getIndex();
  if (!index) return { matches: [] };
  const matches = [];
  for (const file of (payload.files || [])) {
    let src = "";
    try { src = await getRaw(file); } catch (e) { src = ""; }       // 1) fonte AUTOREVOLE: raw al commit
    let basis = "raw";
    if (!src && file.domSource) { src = file.domSource; basis = "dom"; }  // 2) fallback: DOM (vista a file intero)
    if (!src) continue;
    for (const fn of extractFunctions(src)) {
      const h = await codeHash(fn.src);
      if (index[h]) {
        matches.push({ path: file.path, func: fn.name, start: fn.start, end: fn.end,
                       basis: basis, entry: index[h], hash: h });
      }
    }
  }
  return { matches };
}
async function handleVerify(payload, getBuf) {
  return await verifyScarBuf(await getBuf(payload.scarUrl));
}

if (typeof self !== "undefined") { self.SubstrateCore = { codeHash, normalizeCode, extractFunctions, verifyScarBuf, handleScan, handleVerify }; }
