// verify.js — la crittografia della Lente (Pilastro 3) riusata nell'estensione: gunzip + SHA-256 + Ed25519.
// verifyScar(ArrayBuffer) -> {ok, n, refuted:[{input,output,content_hash}], checks}. Zero rete oltre al fetch del file.
(function () {
  const enc = new TextEncoder();
  const hexToBytes = h => { const a = new Uint8Array(h.length / 2); for (let i = 0; i < a.length; i++) a[i] = parseInt(h.substr(i * 2, 2), 16); return a; };
  const bytesToHex = b => Array.from(b).map(x => x.toString(16).padStart(2, "0")).join("");
  async function sha256Hex(bytes) { return bytesToHex(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))); }

  async function gunzip(buf) {
    if (typeof DecompressionStream === "undefined") throw new Error("DecompressionStream non supportato");
    const stream = new Blob([buf]).stream().pipeThrough(new DecompressionStream("gzip"));
    return await new Response(stream).text();
  }
  function deepEqual(a, b) {
    if (a === b) return true;
    if (typeof a !== typeof b || a === null || b === null) return a === b;
    if (Array.isArray(a)) { if (!Array.isArray(b) || a.length !== b.length) return false; for (let i = 0; i < a.length; i++) if (!deepEqual(a[i], b[i])) return false; return true; }
    if (typeof a === "object") { const ka = Object.keys(a), kb = Object.keys(b); if (ka.length !== kb.length) return false; for (const k of ka) if (!deepEqual(a[k], b[k])) return false; return true; }
    return false;
  }
  const stripStamp = c => { const o = {}; for (const k of Object.keys(c)) if (k !== "stamp") o[k] = c[k]; return o; };

  async function verifyCert(env, issuerPub) {
    const out = { hashOk: false, bindOk: false, sigOk: false };
    try {
      if (typeof env.canonical === "string") {
        out.hashOk = (await sha256Hex(enc.encode(env.canonical))) === env.content_hash;
        out.bindOk = deepEqual(JSON.parse(env.canonical), stripStamp(env.certificate));
      }
      const pub = issuerPub || env.pubkey;
      if (env.sig && pub && typeof nacl !== "undefined") {
        out.sigOk = nacl.sign.detached.verify(enc.encode(env.content_hash), hexToBytes(env.sig), hexToBytes(pub));
      }
    } catch (e) { out.err = String(e); }
    out.ok = out.hashOk && out.bindOk && out.sigOk;
    return out;
  }

  async function verifyScar(buf) {
    const bundle = JSON.parse(await gunzip(buf));
    const issuerPub = bundle.pubkey || null;
    const certs = bundle.certs || {};
    let allOk = true, nHash = 0, nSig = 0, nBind = 0, n = 0;
    const refuted = [];
    for (const [ch, env] of Object.entries(certs)) {
      n++;
      const r = await verifyCert(env, issuerPub);
      if (r.hashOk) nHash++; if (r.sigOk) nSig++; if (r.bindOk) nBind++;
      allOk = allOk && r.ok;
      const v = env.certificate.verdict;
      if (v.status === "REFUTED") { const w = v.witness || {}; refuted.push({ input: w.input, output: w.output, content_hash: ch }); }
    }
    return { ok: allOk && n > 0, n, refuted, pubkey: issuerPub, checks: `${nHash}/${n} SHA-256 · ${nSig}/${n} Ed25519 · ${nBind}/${n} binding` };
  }
  window.verifyScar = verifyScar;
})();
