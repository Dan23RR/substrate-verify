"""substrate_core.github_adapter — ADAPTER LIVE GitHub (Pilastro 2): CI/CD zero-trust, ZERO falsi-ALLARME.

Da oracolo PASSIVO a GUARDIANO ATTIVO. Il firehose cattura il codice di un commit -> l'LLM scrive un harness
AVVERSARIALE per quella funzione -> il claim entra nel seam (Contract-Gate + gas-meter) -> il kernel RI-ESEGUE.
  CONFIRMED -> il file e' sicuro (fino a prova contraria empirica).
  REFUTED   -> ALLARME col controesempio ESEGUITO + .scar firmato (ri-verificabile OFFLINE da un terzo).
Il bot non dice mai "penso ci sia un bug": parla SOLO con un controesempio matematicamente girato -> ZERO falsi-
ALLARME per costruzione (un REFUTED porta SEMPRE un controesempio ESEGUITO), RELATIVO alla proprieta' verificata.
ONESTO (recon 2026-06-05): NON garantisce contro i bug MANCATI da un harness debole/aspirazionale (falsi NEGATIVI)
-> quelli diventano ABSTAIN (harness vacuo) o un CONFIRMED-empirical, MAI un falso allarme. Il poster PR e' GUARDATO: dry-run di default,
posta solo con GITHUB_TOKEN da ENV + opt-in esplicito (mai credenziali dalla chat).

Read su repo PUBBLICI funziona senza token. Gli adapter live (mempool Ethereum, ecc.) si innestano allo stesso modo.
"""
from __future__ import annotations

import os
import re
import tempfile
from typing import List, Optional, Tuple

from .prover_seam import submit
from .cert_graph import CertGraph
from .kernel import derive_pubkey
from .export import export_bundle
from .agent import LLMAuditor, ScriptedAuditor, _primary_func, _write_module  # noqa: F401


# ---- 1) FIREHOSE LISTENER: cattura i file sorgente cambiati dall'ultimo commit -------------------------------
def fetch_latest_changed(repo: str, *, ext: Tuple[str, ...] = (".py",), token: Optional[str] = None,
                         ref: Optional[str] = None) -> dict:
    """Ultimo commit di un repo GitHub -> {sha, files:[(path, content)]} dei file cambiati con estensione `ext`.
    Read-only; funziona SENZA token su repo pubblici (GITHUB_TOKEN da ENV per privati/rate-limit)."""
    import requests
    h = {"Accept": "application/vnd.github+json", "User-Agent": "substrate-guardian"}
    tok = token or os.environ.get("GITHUB_TOKEN")
    if tok:
        h["Authorization"] = "Bearer " + tok
    base = "https://api.github.com/repos/%s" % repo
    sha = ref
    if not sha:
        commits = requests.get(base + "/commits", headers=h, timeout=20).json()
        sha = commits[0]["sha"]
    detail = requests.get("%s/commits/%s" % (base, sha), headers=h, timeout=20).json()
    files = []
    for f in detail.get("files", []):
        if f.get("status") != "removed" and f["filename"].endswith(tuple(ext)):
            files.append((f["filename"], requests.get(f["raw_url"], headers=h, timeout=20).text))
    return {"sha": sha, "files": files}


# ---- 2+3) GENERA il claim (L2) e ADJUDICA (L0) --------------------------------------------------------------
def _as_def(name: str, code: str) -> str:
    """Normalizza un frammento nella DEFINIZIONE del nome dato (robusto a 'def name', lambda, espressione nuda)."""
    code = (code or "").strip()
    if not code:
        return ""
    if re.search(r"^\s*def\s+%s\s*\(" % re.escape(name), code, re.M):
        return code                          # gia' un def col nome giusto
    if re.match(r"^\s*def\s+\w+\s*\(", code):
        return code                          # un def (anche nome diverso): lascialo (puo' servire al subject)
    if code.startswith("lambda"):
        return "%s = %s" % (name, code)      # lambda -> assegnala al nome
    return "%s = %s" % (name, code)          # espressione nuda -> assegnala


def audit_source(path: str, content: str, *, key: Optional[bytes] = None, auditor=None, model: Optional[str] = None,
                 workdir: Optional[str] = None, contract: str = "", func_name: Optional[str] = None) -> dict:
    """L'auditor scrive l'harness avversariale per `content`; si assembla (codice committato + subject+prop+gen);
    il claim passa dal SEAM (strip+contract+gas-meter) e il kernel RI-ESEGUE. Ritorna il verdetto + la busta."""
    workdir = workdir or tempfile.mkdtemp(prefix="ghci_")
    auditor = auditor or LLMAuditor(model=model)
    fn = func_name or _primary_func(content)
    h = auditor.audit(content, func_name=fn)
    # Assembla: il CODICE COMMITTATO (definisce la funzione) + l'harness avversariale NORMALIZZATO (subject la chiama).
    module = (content + "\n\n" + _as_def("subject", h.get("subject", "")) + "\n\n"
              + _as_def("prop", h.get("prop", "")) + "\n\n" + _as_def("gen", h.get("gen", "")))
    safe = os.path.basename(str(path)).replace("/", "_").replace("\\", "_") or "commit.py"
    mpath = _write_module(workdir, "audit_" + safe, module)
    params = {"contract": contract} if contract else {}
    env = submit({"domain": "pyprop", "target": mpath, "kind": "invariant", "params": params}, key=key)
    v = env["certificate"]["verdict"]
    return {"path": path, "func": fn, "status": v["status"], "verdict": v, "envelope": env,
            "harness": h, "module_path": mpath}


# ---- 4) INTERVENTO NEL MONDO REALE: l'allarme + il poster GUARDATO -------------------------------------------
def format_alarm(result: dict) -> str:
    """Il commento dell'allarme: un FATTO eseguito, non un'opinione. (Pronto per essere postato sulla PR.)"""
    w = result["verdict"].get("witness") or {}
    return ("❌ Vulnerabilita' FALSIFICATA dal Kernel (controesempio ESEGUITO)\n"
            "File: %s  (funzione: %s)\n"
            "Il controesempio eseguito e':  input = %s  ->  output = %s\n"
            "Proprieta' di correttezza violata. content_hash: %s\n"
            "[Scarica il certificato .scar allegato per ri-verificare CRITTOGRAFICAMENTE offline.]" % (
                result.get("path"), result.get("func"),
                w.get("input"), w.get("output"), result["envelope"]["content_hash"]))


def post_pr_comment(repo: str, pr_number: int, body: str, *, path: Optional[str] = None, line: Optional[int] = None,
                    token: Optional[str] = None, dry_run: bool = True) -> dict:
    """GUARDATO: posta un commento sulla PR SOLO se dry_run=False E un GITHUB_TOKEN e' presente. Default: DRY-RUN
    (non tocca GitHub, ritorna cosa POSTEREBBE). Nessuna credenziale dalla chat: token solo da ENV/parametro."""
    tok = token or os.environ.get("GITHUB_TOKEN")
    if dry_run or not tok:
        return {"posted": False, "dry_run": True, "repo": repo, "pr": pr_number, "path": path, "line": line,
                "would_post": body}
    import requests
    r = requests.post("https://api.github.com/repos/%s/issues/%s/comments" % (repo, pr_number),
                      headers={"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json",
                               "User-Agent": "substrate-guardian"},
                      json={"body": body}, timeout=20)
    return {"posted": r.status_code < 300, "status": r.status_code}


# ---- CODE-HASH canonico per l'OVERLAY UNIVERSALE (Sfida 1): mappa hash-del-codice -> .scar che lo refuta ----
def normalize_code(src: str) -> str:
    """Normalizzazione CANONICA del sorgente, identica lato JS (content-script): CRLF->LF, rstrip per riga
    (solo spazi/tab), trim dei soli newline ai bordi. SHA-256 di questo testo = l'identificatore stabile del codice."""
    s = (src or "").replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(ln.rstrip(" \t") for ln in s.split("\n")).strip("\n")


def code_hash(src: str) -> str:
    """SHA-256 del sorgente normalizzato. Il content-script (codehash.js) calcola lo STESSO valore in JS."""
    import hashlib
    return hashlib.sha256(normalize_code(src).encode("utf-8")).hexdigest()


# ---- IL GUARDIANO: pipeline completa su una lista di file committati ----------------------------------------
def guardian(files: List[Tuple[str, str]], *, key: Optional[bytes] = None, model: Optional[str] = None,
             auditor=None, contract: str = "list[int]", graph: Optional[CertGraph] = None) -> dict:
    """Audita ogni (path, content); ingerisce nel grafo WRITE-GATED; raccoglie gli ALLARMI (REFUTED) coi commenti
    pronti; esporta lo stato come .scar firmato. Niente fiducia: ogni verdetto e' ri-eseguito dal kernel."""
    graph = graph if graph is not None else CertGraph(pubkey=(derive_pubkey(key) if key else None))
    results, alarms = [], []
    for path, content in files:
        r = audit_source(path, content, key=key, auditor=auditor, model=model, contract=contract)
        results.append(r)
        try:
            graph.ingest(r["envelope"])
        except Exception:  # noqa
            pass
        if r["status"] == "REFUTED":
            alarms.append({"comment": format_alarm(r), **r})
    return {"results": results, "alarms": alarms, "graph": graph,
            "scar": export_bundle(graph, key=key, name="github-guardian")}
