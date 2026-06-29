// background.js — il SERVICE WORKER (Manifest V3). Tutta la logica pesante e sensibile alla CSP vive QUI, isolata
// dalla pagina: crypto Ed25519 (nacl), estrazione robusta, fetch dell'indice e del sorgente raw, verifica .scar.
// Il content-script gli parla solo via messaggi. (Pubblica il TUO indice e cambia INDEX_URL.)
importScripts("nacl.min.js", "worker_core.js");

const INDEX_URL = "https://EXAMPLE.github.io/substrate-truth-index/index.json";  // <-- punta al tuo indice pubblico
let _indexCache = null, _indexAt = 0;

async function getIndex() {
  if (_indexCache && Date.now() - _indexAt < 60000) return _indexCache;
  try { _indexCache = await (await fetch(INDEX_URL, { cache: "no-store" })).json(); _indexAt = Date.now(); }
  catch (e) { _indexCache = null; }
  return _indexCache;
}
async function getRaw(file) {
  if (!file.owner || !file.repo || !file.sha || !file.path) return "";   // serve il commit per la fonte AUTOREVOLE
  const url = `https://raw.githubusercontent.com/${file.owner}/${file.repo}/${file.sha}/${file.path}`;
  try { const r = await fetch(url); return r.ok ? await r.text() : ""; } catch (e) { return ""; }
}
function scarUrlOf(entry) {
  if (/^https?:/.test(entry.scar)) return entry.scar;
  return INDEX_URL.replace(/index\.json(\?.*)?$/, "") + entry.scar;
}
async function getBuf(url) { return await (await fetch(url)).arrayBuffer(); }

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      if (msg.type === "scan") {
        const r = await SubstrateCore.handleScan(msg, getIndex, getRaw);
        r.matches.forEach(m => { m.scarUrl = scarUrlOf(m.entry); });
        sendResponse(r);
      } else if (msg.type === "verify") {
        sendResponse(await SubstrateCore.handleVerify(msg, getBuf));
      } else sendResponse({ error: "tipo messaggio sconosciuto" });
    } catch (e) { sendResponse({ error: String(e) }); }
  })();
  return true;   // risposta asincrona
});
