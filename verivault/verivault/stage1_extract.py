"""
verivault.stage1_extract — estrazione di FATTI TIPIZZATI (cio che l'LLM da solo sbaglia, reso esplicito).

Schema-fatti (tassonomia ispirata alle proprieta ERC4626, REIMPLEMENTATE — niente codice AGPL):
  totalAssets_type: 'internal_accounting' (immune a donazione) | 'external_balanceOf' (manipolabile) | 'unknown'
  effective_offset_magnitude: float   # offset EFFETTIVO (0 se OZ non-overridato; 10^k se decimalsOffset=k)
  dead_shares: bool                    # dead-shares / minimum-liquidity al genesis
  donation_vector: bool
  defense_strength: float in [0,1]     # calibrata

DUE estrattori (fusione):
  (A) DETERMINISTICO: prometheus.engines.auto_jacobian (regex/AST) -> fatti grezzi. Veloce, ma CIECO sui
      casi semantici (W5-v1: AUC 0.60, manca l'offset perfino in OZ canonico).
  (B) LLM-FACT-EXTRACTOR (pattern SOTA IRIS): l'LLM legge il sorgente ed estrae i fatti semantici
      (W5-v2: AUC 0.92). E' lo Stadio 1 vero. << QUI va cablato l'LLM dell'host (Anthropic SDK). >>

TODO(Daniel): cablare il client LLM in `extract_facts_llm`. Per ora wrappa l'estrattore deterministico
e lascia il gancio per l'LLM (cosi il pipeline gira end-to-end gia oggi sui fatti deterministici).
"""
from __future__ import annotations
import os, sys
from typing import Any, Optional, Callable

# estrattore deterministico (prometheus) — opzionale, isolato
_AUTOJAC = None
def _load_auto_jacobian():
    global _AUTOJAC
    if _AUTOJAC is None:
        root = os.environ.get("PROMETHEUS_ROOT")
        if root and root not in sys.path:
            sys.path.insert(0, root)
        try:
            from prometheus.engines import auto_jacobian as aj  # type: ignore
            _AUTOJAC = aj
        except Exception:
            _AUTOJAC = False
    return _AUTOJAC


def extract_facts_deterministic(sol_path: str) -> dict[str, Any]:
    aj = _load_auto_jacobian()
    if not aj:
        return {"totalAssets_type": "unknown", "note": "auto_jacobian non disponibile (set PROMETHEUS_ROOT)"}
    try:
        _, _, meta = aj.compute_auto_cri(sol_path)
    except Exception as e:  # noqa
        return {"totalAssets_type": "unknown", "note": f"errore: {e}"}
    return {
        "effective_offset_magnitude": float(meta.get("virtual_shares") or 0),
        "dead_shares": "dead_shares" in (meta.get("defense_markers") or []),
        "donation_vector": bool(meta.get("has_donation_vector")),
        "totalAssets_type": "external_balanceOf" if meta.get("has_donation_vector") else "unknown",
        "defense_strength": 0.5 if meta.get("has_virtual_offset") else 0.0,
        "_source": "deterministic(auto_jacobian)",
    }


FACT_PROMPT = """Sei un esperto di ERC-4626 / cToken share-inflation. Leggi il sorgente e estrai SOLO i fatti
di difesa contro l'attacco first-depositor/donation-inflation, in JSON. CRITICO: distingui il DEFAULT
dall'OVERRIDE (un ERC4626 OZ che NON overrida _decimalsOffset ha offset EFFETTIVO 0 = vulnerabile) e
totalAssets() con accounting INTERNO (immune a donazione) da quello che legge balanceOf/getCash (manipolabile).
Guarda il CODICE, non nomi/commenti. Rispondi SOLO con JSON:
{"totalAssets_type": "internal_accounting"|"external_balanceOf"|"unknown",
 "effective_offset_magnitude": <float, 0 se assente/non-overridato>,
 "dead_shares": <bool>, "donation_vector": <bool>, "defense_strength": <float 0..1>}

SORGENTE:
"""

def extract_facts_llm(src: str, model: str = "claude-sonnet-4-5", client: Any = None) -> dict[str, Any]:
    """Estrattore semantico W5-v2 (AUC 0.92) via Anthropic SDK. La key SOLO da env ANTHROPIC_API_KEY,
    MAI incollata in chat/codice. Per uso interattivo, l'estrazione si fa anche via il meccanismo
    workflow/agent (che e' gia l'LLM) — vedi eval/ del progetto di ricerca."""
    import os, json as _json
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("Imposta ANTHROPIC_API_KEY come VARIABILE D'AMBIENTE (mai in chat/codice).")
    if client is None:
        import anthropic  # type: ignore
        client = anthropic.Anthropic(api_key=key)
    msg = client.messages.create(model=model, max_tokens=600,
                                 messages=[{"role": "user", "content": FACT_PROMPT + src[:60000]}])
    txt = msg.content[0].text
    start, end = txt.find("{"), txt.rfind("}")
    return _json.loads(txt[start:end + 1]) if start >= 0 else {"totalAssets_type": "unknown"}


# gancio per l'LLM-fact-extractor (lo Stadio 1 reale, W5-v2). Inietta una funzione (source)->facts.
LLMFactFn = Callable[[str], dict[str, Any]]

def extract_facts(sol_path: str, llm_fact_fn: Optional[LLMFactFn] = None) -> dict[str, Any]:
    """Se fornito llm_fact_fn (Anthropic SDK), usa l'estrattore SEMANTICO (W5-v2, AUC 0.92). Altrimenti OFFLINE:
    l'estrattore STRUTTURALE deterministico (extract_solidity, no API/PROMETHEUS) per i pattern ERC-4626 comuni;
    se 'unknown', tenta auto_jacobian (PROMETHEUS_ROOT). Mai un finto-fatto: 'unknown' -> il pipeline ASTIENE."""
    src = open(sol_path, encoding="utf-8", errors="ignore").read()
    if llm_fact_fn is not None:
        facts = llm_fact_fn(src)
        facts["_source"] = "llm_fact_extractor"
        return facts
    from .extract_solidity import extract_facts_solidity           # OFFLINE strutturale (primario)
    facts = extract_facts_solidity(src)
    if facts.get("totalAssets_type") == "unknown":
        det = extract_facts_deterministic(sol_path)                # secondario: auto_jacobian (se PROMETHEUS_ROOT)
        if det.get("totalAssets_type") not in (None, "unknown"):
            return det
    return facts
