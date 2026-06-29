"""substrate_core.codeextract — estrazione ROBUSTA di funzioni dal sorgente COMPLETO (la fine dell'euristica).

Il content-script NON hasha il DOM frammentato di una PR. Il demone e l'estensione estraggono le funzioni dal
sorgente AUTOREVOLE (il file raw al commit) con QUESTO stesso algoritmo (gemello in worker_core.js), poi
confrontano i code_hash -> combaciano per costruzione. Indentazione + tracking dei triple-quote = robusto a
commenti che contengono 'def', docstring multilinea, stringhe ingannevoli, funzioni multiple.

(tree-sitter-WASM e' l'upgrade opzionale per la fedelta' multi-linguaggio; qui l'estrattore Python, estendibile.)
"""
from __future__ import annotations


def _scan_strings(lines):
    """Per ogni riga: True se la riga INIZIA dentro un triple-quoted string. Toggle pragmatico su ''' e \"\"\"."""
    res, in_str = [], None
    for ln in lines:
        res.append(in_str is not None)
        idx = 0
        while True:
            t1 = ln.find("'''", idx)
            t2 = ln.find('"""', idx)
            cands = [(t, d) for t, d in ((t1, "'''"), (t2, '"""')) if t >= 0]
            if not cands:
                break
            pos, delim = min(cands)
            if in_str is None:
                in_str = delim
            elif in_str == delim:
                in_str = None
            idx = pos + 3
    return res


def extract_functions(source: str):
    """Funzioni top-level dal sorgente COMPLETO Python: [{name, start, end, src}] (start/end = indici-riga, end escl.).
    Un 'def'/'async def' fuori da una stringa apre una funzione; il corpo va fino al primo dedent (saltando vuoti e
    righe-stringa). Un 'def' dentro un commento (#) o una stringa NON apre una funzione."""
    s = (source or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = s.split("\n")
    sstr = _scan_strings(lines)
    out, i, n = [], 0, len(lines)
    while i < n:
        ln = lines[i]
        st = ln.lstrip()
        if (not sstr[i]) and (st.startswith("def ") or st.startswith("async def ")):
            indent = len(ln) - len(st)
            name = st.split("(", 1)[0].replace("async def", "").replace("def", "").strip()
            j = i + 1
            while j < n:
                lj = lines[j]
                if lj.strip() == "" or sstr[j]:
                    j += 1
                    continue
                if (len(lj) - len(lj.lstrip())) <= indent:
                    break
                j += 1
            end = j
            while end - 1 > i and lines[end - 1].strip() == "":
                end -= 1
            out.append({"name": name, "start": i, "end": end, "src": "\n".join(lines[i:end])})
            i = j
        else:
            i += 1
    return out
