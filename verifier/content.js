// content.js — lo SCANNER "STUPIDO" (Manifest V3). Nessuna crypto, nessun indice, nessun nacl: solo DOM.
// Legge i file/righe della PR, manda i dati al SERVICE WORKER via chrome.runtime.sendMessage, riceve DOVE
// iniettare, e disegna il banner. Al click chiede al worker la verifica del .scar e mostra il pannello.
// Isolato dal main-thread pesante e dalla Content-Security-Policy di GitHub (il worker gira nel contesto estensione).
(function () {
  function rowsFrom(scope) {
    return Array.from(scope.querySelectorAll(".blob-code-inner")).map(el => {
      const tr = el.closest("tr");
      const num = tr ? tr.querySelector(".blob-num, .blob-num-addition, [data-line-number]") : null;
      const lineNo = num ? parseInt((num.getAttribute && num.getAttribute("data-line-number")) || num.textContent.trim() || "0", 10) : 0;
      return { text: el.textContent, lineNo: lineNo, tr: tr };
    });
  }
  function repoMeta() {
    const m = location.pathname.match(/^\/([^\/]+)\/([^\/]+)\/(?:pull|blob|commit)/);
    let sha = "";
    const oid = document.querySelector("[data-commit-oid]");
    if (oid) sha = oid.getAttribute("data-commit-oid") || "";
    if (!sha) { const bm = location.pathname.match(/\/blob\/([0-9a-f]{7,40})\//); if (bm) sha = bm[1]; }
    return { owner: m ? m[1] : "", repo: m ? m[2] : "", sha: sha };
  }
  function readFiles() {
    const meta = repoMeta();
    const containers = document.querySelectorAll("[data-tagsearch-path], .file, .js-file, .file-head");
    const files = [];
    if (containers.length) {
      const seen = new Set();
      containers.forEach(fe => {
        const scope = fe.closest(".file") || fe.parentElement || fe;
        if (seen.has(scope)) return; seen.add(scope);
        const path = (fe.getAttribute && fe.getAttribute("data-tagsearch-path")) ||
          (fe.querySelector && (fe.querySelector(".file-info a") || {}).title) ||
          (fe.textContent || "").trim();
        const rows = rowsFrom(scope);
        if (rows.length) files.push({ path: (path || "file").trim(), rows: rows, owner: meta.owner, repo: meta.repo, sha: meta.sha });
      });
    }
    if (!files.length) {
      const rows = rowsFrom(document);
      if (rows.length) files.push({ path: "file", rows: rows, owner: meta.owner, repo: meta.repo, sha: meta.sha });
    }
    return files;
  }

  const files = readFiles();
  if (!files.length) return;
  const payload = files.map(f => ({ path: f.path, owner: f.owner, repo: f.repo, sha: f.sha, domSource: f.rows.map(r => r.text).join("\n") }));

  send({ type: "scan", files: payload }, (res) => {
    if (!res || !res.matches) return;
    res.matches.forEach(m => { const f = files.find(x => x.path === m.path) || files[0]; if (f) injectBanner(f, m); });
  });

  function injectBanner(file, m) {
    let row = null;
    if (m.basis === "dom" && file.rows[m.end - 1]) row = file.rows[m.end - 1].tr;
    else {
      let best = null;
      file.rows.forEach(r => { if (r.lineNo >= m.start + 1 && r.lineNo <= m.end) { if (!best || r.lineNo > best.lineNo) best = r; } });
      row = best ? best.tr : (file.rows[file.rows.length - 1] || {}).tr;
    }
    if (!row || !row.parentNode) return;
    if (row.parentNode.querySelector('.substrate-banner-row[data-h="' + m.hash + '"]')) return;
    const tr = document.createElement("tr");
    tr.className = "substrate-banner-row"; tr.setAttribute("data-h", m.hash);
    const colspan = (row.children && row.children.length) || 2;
    tr.innerHTML = '<td colspan="' + colspan + '" style="padding:0"><div class="substrate-banner"><span class="sb-dot"></span>' +
      '<b>[!] VULNERABILITÀ DIMOSTRATA dal Kernel</b> — <code>' + esc(m.func || "") + '</code> refutata con un ' +
      'controesempio ESEGUITO. <span class="sb-act">Clicca per ri-verificare nel tuo browser ▸</span></div></td>';
    row.parentNode.insertBefore(tr, row.nextSibling);
    tr.querySelector(".substrate-banner").addEventListener("click", () => doVerify(m));
  }

  function doVerify(m) {
    openPanel(m, { loading: true });
    send({ type: "verify", scarUrl: m.scarUrl }, (res) => openPanel(m, res || { error: "nessuna risposta dal worker" }));
  }
  function esc(s) { return String(s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }
  function openPanel(m, res) {
    let p = document.getElementById("substrate-panel");
    if (!p) { p = document.createElement("div"); p.id = "substrate-panel"; document.body.appendChild(p); }
    if (res.loading) { p.innerHTML = '<div class="sp-head bad">Ri-verifico nel tuo browser…</div>'; p.classList.add("show"); return; }
    const ok = res && res.ok;
    const ref = res && res.refuted && res.refuted[0];
    p.innerHTML =
      '<div class="sp-head ' + (ok ? "ok" : "bad") + '">' + (ok ? "✔ Verificato dal tuo computer" : "⚠ Verifica fallita") +
      '<span class="sp-x" id="sp-x">×</span></div><div class="sp-body">' +
      '<div class="sp-k">Funzione</div><div class="sp-v"><code>' + esc(m.func || "") + '</code></div>' +
      '<div class="sp-k">Verdetto del kernel</div><div class="sp-v"><span class="sb-badge">REFUTED</span> · controesempio eseguito</div>' +
      (ref ? '<div class="sp-k">Input fatale (eseguito)</div><div class="sp-v sp-wit">input ' + esc(String(ref.input)) +
        ' &nbsp;→&nbsp; output ' + esc(String(ref.output)) + '</div>' : "") +
      '<div class="sp-k">Crittografia ricalcolata QUI (nel service worker)</div><div class="sp-v">' + esc(res.checks || res.error || "") + '</div>' +
      '<div class="sp-note">Ri-verificato dal tuo browser un attimo fa · zero fiducia in alcun server.</div></div>';
    p.classList.add("show");
    const x = document.getElementById("sp-x"); if (x) x.onclick = () => p.classList.remove("show");
  }

  // TRASPORTO: chrome.runtime (estensione reale) oppure lo shim in-page (demo).
  function send(msg, cb) {
    if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) chrome.runtime.sendMessage(msg, cb);
    else if (typeof window !== "undefined" && window.__SUBSTRATE_SHIM__) window.__SUBSTRATE_SHIM__(msg).then(cb);
  }
})();
