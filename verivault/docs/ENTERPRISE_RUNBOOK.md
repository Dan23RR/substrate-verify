# VeriVault — ENTERPRISE RUNBOOK (turnkey)

> Stato: il **nucleo-prodotto è L4 e self-contained** (`python verify_all.py` → ALL GREEN, 21 check). I 4 pilastri
> enterprise restanti sono **infra-gated**, NON engineering-gated: i RUNNER esistono e sono testati; manca solo la
> risorsa (credenziale/RPC/dataset). Qui sotto, per ogni pilastro: la risorsa, il **comando esatto** una volta fornita,
> il numero-target che lo porterebbe a L4, e cosa lo falsificherebbe. Niente è finto: do i runner pronti, non i run.

## Pilastro (a) — Death-gate su set vergine INDIPENDENTE
- **Macchina:** PRONTA e testata OFFLINE (`eval/test_death_gate_runner.py`: estrai→score→recall@FP=0/AUC su contratti reali
  via l'estrattore deterministico; AUC=1.0/recall=1.0 su N=5, *suggestivo non conclusivo*).
- **Risorsa mancante:** un dataset di **≥40–60 contratti share-accounting INDIPENDENTI, ≥20 SAFE**, con label a base documentata.
  Assemblabile con: `ANTHROPIC_API_KEY` (estrattore W5-v2 semantico, superiore allo strutturale) **oppure** una raccolta di
  sorgenti reali su disco (l'estrattore strutturale offline basta per i pattern comuni).
- **Comando:** `python eval/death_gate.py <manifest.json> <labels.json>`  (manifest = `[{"id","path"}]`, labels = `{id: "VULNERABLE"|"SAFE"}`).
- **L4-target / Killer (pre-registrato, `eval/prereg.md`):** recall@FP=0 > 0.636 AND AUC > 0.75 sul vergine → GO; altrimenti
  **NO-GO** (lo scorer resta cost-router, l'exec-gate resta l'adjudicatore sound — esito già accettato).

## Pilastro (b) — Stage-3: auto-generazione harness/PoC da sorgente mai-vista
- **Fatto offline:** estrazione-fatti deterministica (`extract_solidity.py`) + harness **PARAMETRICO-fedele** (`GeneralGate._oneAttack`
  chiama l'ABI reale via `IVault` — adjudica QUALSIASI vault IVault-compatibile **senza nuovo harness**).
- **Risorsa mancante:** `ANTHROPIC_API_KEY` per l'orchestratore che adatta l'harness a interfacce NON-`IVault` (collo di bottiglia industria).
- **Comando (quando c'è la key):** cablare `extract_facts_llm` (SDK env-var) in `audit_signed(..., llm_fact_fn=extract_facts_llm)`.
- **Killer:** l'harness generato produce FP>0 (un PoC che non viola davvero) → si retrocede all'harness parametrico-scritto.

## Pilastro (c) — Coupled-forge (composizione) — ✅ FATTO (L4)
- `gate/test/CoupledGate.t.sol` + `OracleCoupledGate.t.sol` (PASS): vault-interno regge; oracolo-AMM super-additivo +78e21;
  `algebra.monotone_from_dependency` declassa ad ABSTAIN. Nessuna risorsa mancante.

## Pilastro (d) — Head-to-head vs A1 / aether
- **Risorsa mancante:** gli OUTPUT reali di A1 (arXiv 2507.05558) / aether sui loro set (richiede eseguire i loro tool / i loro artefatti).
- **Comando:** su un set comune, eseguire i loro PoC + `audit_signed` di VeriVault; misurare l'ADD = #safe-cert + #ABSTAIN-calibrati
  che il paradigma positives-only NON emette, a parità di FP. (Una "simulazione" del baseline sarebbe tautologica → NON fornita.)
- **Killer:** nessun ADD misurabile (safe-cert / riduzione-FP) vs A1/aether su un set comune.

## Pilastro (e) — Productization — ✅ FATTO offline (live = RPC)
- `audit_signed(source)` → **certificato firmato portabile** (`eval/test_product_flow.py`); `audit_onchain(addr)` API onesta
  (ABSTAIN senza RPC); signer/portabilità (`certificate.py`); `pyproject` extra; CI (`.github/workflows/verify.yml`); `verify_all.py`.
- **Risorsa mancante (solo per il live):** `ETH_RPC_URL` (archive node).
- **Comando (live):** `ETH_RPC_URL=<rpc> python -c "import verivault as v; print(v.audit_onchain('0x...', '<gate_dir>', 'test/BenchGate.t.sol', '<key>'))"`
  oppure `ETH_RPC_URL=<rpc> forge test --match-path test/BenchGate.t.sol` (i 22 vault mainnet).
- **Killer:** un `VULN` on-chain con profit≤0 ri-eseguito (FP) → il fork-gate non è sound on-chain.

---
*Tutto ciò che è offline è verde in `verify_all.py`. I pilastri sopra sono pre-wired: dato il resource, ognuno è un comando.*
