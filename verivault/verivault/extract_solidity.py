"""
verivault.extract_solidity — estrattore di FATTI TIPIZZATI DETERMINISTICO da sorgente Solidity (OFFLINE, no API, no PROMETHEUS_ROOT).

Colma il gap (b) per i pattern STRUTTURALI comuni senza l'LLM: parsing robusto (regex strutturali) dei marcatori di
difesa anti-inflation ERC-4626. Scope ONESTO (scope-naming): copre i pattern strutturali ricorrenti
  - totalAssets() override che legge balanceOf/getCash/exchangeRate  -> external_balanceOf (manipolabile)
  - totalAssets() override che ritorna un accumulatore interno        -> internal_accounting (immune a donazione)
  - eredita OZ/Solady ERC4626 senza override                         -> external_balanceOf + virtual-shares (difeso)
  - _decimalsOffset() -> k                                            -> offset 10^k
  - mint a address(0)/dead nel constructor                           -> dead_shares
Sui casi SEMANTICI ambigui (logica non riconducibile a questi pattern) ritorna totalAssets_type='unknown' -> il pipeline
ASTIENE (mai un finto-fatto). Quando ANTHROPIC_API_KEY c'e', extract_facts_llm resta l'estrattore semantico superiore.
"""
from __future__ import annotations
import re
from typing import Any


def _total_assets_body(src: str) -> str | None:
    """estrae il corpo di function totalAssets(...) {...} se overridato (brace-matching semplice)."""
    m = re.search(r"function\s+totalAssets\s*\([^)]*\)[^\{]*\{", src)
    if not m:
        return None
    i = m.end() - 1
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i + 1:j]
        j += 1
    return src[i + 1:]


def _inherits_virtual_base(src: str) -> bool:
    """eredita una base ERC4626 con virtual-shares (OZ o Solady)? (base.totalAssets legge balanceOf ma difende con virtual)"""
    return bool(re.search(r"@openzeppelin|openzeppelin-contracts|OZERC4626|SoladyERC4626|solady/tokens/ERC4626", src))


def extract_facts_solidity(src: str) -> dict[str, Any]:
    body = _total_assets_body(src)
    facts: dict[str, Any] = {"_source": "deterministic(structural-solidity)"}

    # --- totalAssets_type ---
    if body is not None:
        if re.search(r"\.balanceOf\s*\(\s*address\s*\(\s*this\s*\)\s*\)", body) or re.search(r"getCash|exchangeRate", body):
            tat = "external_balanceOf"
        elif re.search(r"return\s+([A-Za-z_]\w*)\s*;", body) and not re.search(r"balanceOf", body):
            ident = re.search(r"return\s+([A-Za-z_]\w*)\s*;", body).group(1)
            # FP=0 (review): un accumulatore e' 'internal' SOLO se NON e' sincronizzato da un balance ESTERNO altrove
            # nel sorgente (es. sync(){ _ta = asset.balanceOf(this); }) -> in tal caso e' manipolabile via donazione+sync
            # -> NON internal. Nel dubbio: 'unknown' -> defense_risk ASTIENE (mai un finto-internal = falso-SAFE).
            synced = re.search(re.escape(ident) + r"\s*(?:=|\+=|-=)\s*[^;]*(?:balanceOf|getCash|exchangeRate)", src)
            tat = "unknown" if synced else "internal_accounting"
        else:
            tat = "unknown"
    elif _inherits_virtual_base(src) and re.search(r"\bis\b[^\{]*ERC4626", src):
        tat = "external_balanceOf"           # base OZ/Solady: totalAssets = asset.balanceOf(this)
    else:
        tat = "unknown"                      # base astratta (solmate richiede override) o pattern non riconosciuto
    facts["totalAssets_type"] = tat

    # --- virtual-shares + offset effettivo ---
    has_virtual_base = _inherits_virtual_base(src)
    explicit_balanceof_override = (body is not None and re.search(r"\.balanceOf\s*\(\s*address\s*\(\s*this\s*\)\s*\)", body) is not None)
    # un override esplicito che legge balanceOf BYPASSA la difesa virtual della base -> raw manipolabile
    virtual = has_virtual_base and not explicit_balanceof_override
    mo = re.search(r"function\s+_decimalsOffset\s*\([^)]*\)[^\{]*\{[^}]*return\s+(\d+)", src)
    if mo:
        k = int(mo.group(1)); offset_mag = float(10 ** k)
    elif virtual:
        offset_mag = 1.0                     # virtual-shares default (offset 0 -> +1)
    else:
        offset_mag = 0.0
    facts["effective_offset_magnitude"] = offset_mag

    # --- dead-shares ---
    facts["dead_shares"] = bool(re.search(r"_mint\s*\(\s*(address\s*\(\s*0\s*\)|0x0{1,40}|0x[dD][eE][aA][dD])", src))

    # --- donation_vector + defense_strength (derivati, coerenti con stage2_score) ---
    facts["donation_vector"] = (tat == "external_balanceOf")
    if tat == "internal_accounting":
        ds = 0.9
    elif tat == "external_balanceOf":
        if offset_mag >= 1000 or facts["dead_shares"]:
            ds = 0.9
        elif virtual:
            ds = 0.5                          # virtual +1: il gate prova immune ma lo scorer resta cauto (la prova vince)
        else:
            ds = 0.0                          # raw balanceOf, nessuna difesa -> rischio alto
    else:
        ds = 0.0
    facts["defense_strength"] = ds
    return facts
