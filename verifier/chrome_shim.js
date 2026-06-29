// chrome_shim.js — SOLO PER LA DEMO: simula chrome.runtime.sendMessage instradando ai gestori di worker_core
// IN-PAGE (cosi' la pagina-mock prova l'architettura a messaggi senza caricare l'estensione in Chrome).
// Nell'estensione REALE questo file NON esiste: i messaggi vanno al vero service worker (background.js).
(function () {
  const INDEX_URL = window.__INDEX_URL__ || "./data/index.json";
  const SCAR_BASE = window.__SCAR_BASE__ || "./";
  let idx = null;
  async function getIndex() { if (idx) return idx; idx = await (await fetch(INDEX_URL, { cache: "no-store" })).json(); return idx; }
  async function getRaw(file) {
    if (!file.owner || !file.repo || !file.sha) return "";   // demo: nessun repo reale -> "" -> il worker usa domSource
    const url = `https://raw.githubusercontent.com/${file.owner}/${file.repo}/${file.sha}/${file.path}`;
    try { const r = await fetch(url); return r.ok ? await r.text() : ""; } catch (e) { return ""; }
  }
  async function getBuf(url) { return await (await fetch(url)).arrayBuffer(); }
  window.__SUBSTRATE_SHIM__ = async function (msg) {
    if (msg.type === "scan") {
      const r = await SubstrateCore.handleScan(msg, getIndex, getRaw);
      r.matches.forEach(m => { m.scarUrl = /^https?:/.test(m.entry.scar) ? m.entry.scar : SCAR_BASE + m.entry.scar; });
      return r;
    }
    if (msg.type === "verify") return await SubstrateCore.handleVerify(msg, getBuf);
    return { error: "tipo sconosciuto" };
  };
})();
