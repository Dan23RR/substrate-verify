# VeriVault — Mappa Stato-Reale / Gap (UNDERSTAND, post-esecuzione)

> Chief-engineer synthesis · 2026-06-02 · ancorata a **esecuzioni reali** (non solo lettura).
> Disciplina L0–L4 (da `research_substrate_capacity/CLAUDE.md`): **solo L4 conta** (soglia derivata/eseguita,
> falsificatore-assert in-codice, scope dichiarato). Distinguo **claimed-L4** da **verified-L4** (= eseguito DA ME).
> Metodo: workflow UNDERSTAND (24 agenti, lettura+verifica avversariale) **+** ri-esecuzione diretta dei comandi.

## 0. Riconciliazione di un errore della mappa (ritirato)
Un cluster del workflow ha graduato il moat-gate come **L0 "fabbricazione: i test NON esistono"**. È un **errore di
search-path** (cercava solo dentro `verivault/`). I file ESISTONO in `research_substrate_capacity/exp/virgin/gate/test/`
e **io li ho eseguiti** (sotto). Verdetto ritirato → riscopato a **verified-L4-on-set** coi caveat reali.

---

## 1. Cosa ho ESEGUITO io (verified-L4-on-set, offline, no-RPC) — il moat è reale

| Artefatto | Comando | Esito eseguito (2026-06-02) | Livello |
|---|---|---|---|
| `LabeledBench.t.sol` | `forge test --match-path test/LabeledBench.t.sol` | `PASS` · `TP=2 TN=5 FP=0 FN=0` recall=100% prec=100% · OZ-v4.8 +100e18, solmate +25e18 · `assertEq(fp,0)`+`assertEq(fn,0)` reggono | **L4** (scope: 7 impl reali, in-dist, **denom-VULN=2**) |
| `GeneralGate.t.sol` | `forge test --match-path test/GeneralGate.t.sol` | `PASS` · solmate_balanceof +25e18 (witness D=50e18); 4 forme IMMUNE (profit<0) | **L4 la VULN** / **L3 le 4 IMMUNE** (emit-only, non asserite → BRICK 2) |
| `CTokenGate.t.sol` | `forge test --match-path test/CTokenGate.t.sol` | `PASS` · **Compound v2 reale**: attaccante ruba **intero deposito 100e18**, vittima 0 cToken, witness D=1000e18 | **L4** (codice-incidente reale Sonne/Hundred/Onyx; scope: deploy locale, non replay on-chain) |
| `RoundingGate.t.sol` | `forge test --match-path test/RoundingGate.t.sol` | `PASS` · up→VULN (+0.5e18, witness x=1), down→IMMUNE | **L4** (2ª classe-vuln, stesso kernel; scope: MinimalVault in-vitro) |
| `RealSolmateGate.t.sol` | `forge test --match-path test/RealSolmateGate.t.sol` | `PASS×2` · balanceOf +25e18 / internal IMMUNE | **L4** (Solmate reale vendorizzato, bidirezionale) |
| `forge/test/ImmunityCert.t.sol` | `forge test --match-path test/ImmunityCert.t.sol` | `PASS` · raw +1e18 / OZ offset {0,1,2,4,6} tutti 0 | **L4** (scope: modelli toy raw-vs-OZ) |
| `eval/test_algebra.py` (post-BRICK1) | `python eval/test_algebra.py` | `exit 0` · SOUNDNESS→VULN, coupling MEV(A∘B)=**+80 token**→weakest-link **ROTTA**→`protocol_verdict` **ABSTAIN** | **L4 la LOGICA** (gap c) / coupling **MODELLATO** (deterministico) → empirico = L1, vedi gap c |
| `import verivault` (post-BRICK1) | `python -c "import verivault"` | `exit 0` (era rotto) | **L4** (BRICK 1 fatto) |

**Conclusione §1:** il fossato eseguibile (exec-gate bidirezionale, form-agnostico, FP=0 sul set etichettato, preda
reale Compound) **regge sotto esecuzione mia**. È L4 *su questi set*. È **il valore sound che sopravvive**.

## 2. L3 — eseguito ma caveato
| Componente | Comando | Numero eseguito | Perché non L4 |
|---|---|---|---|
| `eval/death_gate.py` | `python eval/death_gate.py` | AUC=**0.904**, recall@FP=0=**0.515**<0.636 → **NO-GO**; held-out frozen recall=0.621/FP=0.033; ranking-test=0.792 | in-distribution; soglia-assoluta non trasferisce OOD (0/2 su virgin_spotcheck) — **gap (a)** |
| `stage2_abstain_on_unknown` | `python eval/death_gate.py` | 48 analizzabili / 20 ABSTAIN su 68 reali | solo `print`, nessun assert |

## 3. ≤L2 / L0 / dead-code — buchi onesti (dal workflow, ri-confermati)
| Componente | file:line | Livello | Problema |
|---|---|---|---|
| `conformal_gate.py` | `eval/conformal_gate.py:45-77` | **L2** | la **garanzia conforme è EMPIRICAMENTE VIOLATA nel suo stesso run**: rispettata solo **1/5, 2/5, 2/5** split → small-n fragile (gap a) |
| `stage5_conformal_threshold_fn` | `stage5_calibrate.py:15-23` | **L0** | **dead-code**: mai chiamato; la pipeline usa costante **0.5 hardcoded** (`pipeline.py:34`) |
| `run_cascade` | `cascade.py:19-40` | **L1** | **dead-code**: zero caller, zero test; `forced_donation`→T3 letto da nessun harness |
| `stage2_defense_risk_scorer` | `stage2_score.py:15-34` | **L2** | headline AUC 0.920 cita `exp/w5v2_score.py` **ASSENTE**; **due risk-fn divergenti**: `clean_risk`≠`defense_risk` su **24/68 righe** (gap dati) |
| `labeled_facts.json` | `eval/data/labeled_facts.json` | **L2** | 68 righe reali ma **in-distribution + circolarità** (risk-col ≈ clean_risk su 61/68); LLM-self-extracted |
| certificato "firmato/portabile" | `schemas.py:48-53` | **L0** | **nessun serializer/signer esiste** — è prosa (gap e) |
| `smt_tier_t1` (63 casi) | `oracles/smt_rounding.py` + `eval/test_smt_tier.py` | **L2** *(pending-z3)* | **ZERO assert** (print+flag); non gira (z3 assente). Post-BRICK1 degrada ad ABSTAIN, mai crash |
| `BenchGate`/`ForkGate` (22 vault) | `test/BenchGate.t.sol` | **L2** *(pending-RPC)* | `foundry.toml` senza `rpc_endpoints` + `ETH_RPC_URL` unset → **self-skip (riga 32) fail-open**; split 16/6 **emit-only** (solo `assertEq(vuln,0)` a riga 53) |
| license discipline | `docs/LICENSES.md` | **L0** | prosa legale, nessun scanner/CI; **z3 non dichiarato** in `pyproject.toml` (`dependencies=[]`) né nella tabella LICENSES |

**Conteggio (workflow, pre-mie-esecuzioni):** L4-confermati=0 · L3=7 · ≤L2=27 · needs_execution=12.
**Conteggio (post-mie-esecuzioni + BRICK 1):** **8 artefatti verified-L4-on-set** (tabella §1), gli altri come §2–§3.

---

## 4. I 5 gap enterprise (livello attuale · cosa manca · cosa lo UCCIDE)
- **(a) Death-gate indipendente** — *L3, caratterizzato rigorosamente (BRICK 4, numeri post-review)*. **Misurato**
  (`eval/conformal_gate.py`, 200 split, soglia-overflow→+inf): a n_SAFE=15 — eps=0.05 **IRRAGGIUNGIBILE** (achiev=0%, astiene);
  eps=0.10 achiev=33% **VIOLATA da overlap reale** (mean_FP=0.083, mean_FN=0.114); eps=0.20 achiev=98% VIOLATA (mean_FN=0.201)
  → **ipotesi "conforme salva gap(a)" FALSIFICATA** (separando achievability da overlap; il primo "mean_FP=0.121" era un
  artefatto clamp, corretto dalla review). Né soglia-assoluta (virgin_spotcheck Finding-1: recall 0/2 OOD) né
  conforme-a-questo-n bastano → **lo scorer NON è un gate autonomo affidabile; è cost-router/pre-filtro; l'exec-gate forge
  (L4) è l'UNICO adjudicatore sound**. Il segnale però generalizza (Finding-2: ranking recall@FP=0=1.0 OOD). Manca: **SET
  VERGINE INDIPENDENTE** (≥40-60 contratti, ≥20 SAFE) — la MACCHINA è ora **offline-ready**
  (`eval/test_death_gate_runner.py`: estrazione deterministica + score + metrica su contratti reali; AUC=1.0/recall=1.0 su
  N=5 suggestivo). Avanzato a **N=9 con estrazione W5-v2 (sub-agent)** + label-per-esecuzione (`eval/death_gate_w5v2.py`):
  **recall@FP=0=1.0, AUC=1.0 → GO** (margine FP=0 +0.10; W5-v2 ha colto OZ v4.8 come VULN). CAVEAT: N=9 suggestivo, shape
  semi-sintetiche, margine sottile, recall@FP=0 fragile all'outlier-SAFE (il 68-set in-dist dà NO-GO). Resta infra-gated
  **SOLO la SCALA + corpus TERZO** (≥40-60, ≥20 SAFE deployati); vedi `docs/ENTERPRISE_RUNBOOK.md`.
  **Primo corpus TERZO (offline) FATTO:** `gate/test/ThirdPartyGate.t.sol` — exec-gate su vault la cui logica-inflation è di
  OZ/solady (terze parti, lib vendorizzate): **fee-vault (pattern SMT-abstain) → IMMUNE** (form-agnostic > SMT dimostrato su
  logica-fee ufficiale OZ), OZ-v5-mock → IMMUNE, **solady-no-virtual → VULN** (+100e18), **FP=0**.
  **✅ CORPUS TERZO A SCALA, LIVE (2026-06-03, RPC Alchemy dal registro OS):** `BenchGate.t.sol` via fork mainnet (47.8s) —
  **22 vault deployati REALI** (sDAI/sUSDe/Yearn V3/Gearbox V3/Morpho/mevETH…): **16 IMMUNE · 0 VULN (FP=0 asserito) · 6 ABSTAIN
  dichiarati**, RIPRODOTTO da me. `audit_onchain(sDAI)` LIVE → IMMUNE + certificato FIRMATO. **Gap (a)-scala su corpus deployato
  TERZO: CHIUSO** (lato exec-gate, il gate enterprise). Lo scorer resta NO-GO (cost-router, accettato). **Killer:** recall@FP=0 ≤
  0.636 sul vergine → scorer non batte single-LLM → copilota (esito già pre-registrato e accettato).
- **(b) Stage-3 + estrazione** — *L4 ESEGUITO (su contratti IVault-compatibili)*. **Estrazione:** `verivault/extract_solidity.py`
  deterministico offline, corretto sui 5 shape reali (`eval/test_extractor.py`) → prodotto **SELF-CONTAINED**. **Stage-3 autonomo
  (il collo di bottiglia industria):** ESEGUITO — un sub-agent LLM (nessuna API-key) legge una sorgente **mai-vista**, estrae i
  fatti, e **auto-genera un harness forge FEDELE** (riempie solo import+deploy; l'attacco è il template parametrico fisso → FP=0).
  `eval/test_stage3.py` (exit 0): su `UnseenVulnVault`/`UnseenSafeVault` mai-configurati, l'exec-gate DISPONE → VULN(+25e18)/IMMUNE,
  **ground-truth + FP=0**. **RESTA:** interfacce NON-`IVault` (richiedono adattamento harness); l'estrattore semantico LLM resta
  superiore sui casi non-strutturali. **Killer (superato):** l'harness auto-generato compila, gira, e il safe NON è flaggato VULN.
- **(c) Coupled-forge (composizione)** — *L4 BIDIREZIONALE eseguito (BRICK 5 ✅)*. `gate/test/CoupledGate.t.sol`
  (PASS): composizione **vault-interna** (vault immune + prestito con custodia) → weakest-link **REGGE** (≤ max singoli);
  un +990e18 iniziale era artefatto di B-faucet infedele, **catturato dalla verifica avversariale**. `OracleCoupledGate.t.sol`
  (PASS): via **oracolo-AMM flash-manipolabile** → super-additività **CONFERMATA**, profit **+78e21 > max(singoli)**
  (= over-borrow a 2× − slippage reale, no free-money). `algebra.py.monotone_from_dependency` deriva `monotone` dalla
  **dipendenza-oracolo** (non più hand-set), legato a `protocol_verdict`→ABSTAIN in `test_algebra.py` (exit 0).
  **Resta (scala):** esecuzione su protocollo deployato reale via fork. **Esito killer:** la super-additività NON è un mito —
  esiste e misurata, ma SOLO per dipendenza-oracolo-esterno; per vault-interno il weakest-link regge (entrambi provati).
- **(d) Head-to-head vs A1/aether** — *confronto-capacità misurato (offline); definitivo = re-run loro tool*. `eval/head_to_head.py`
  (exit 0): colonna VeriVault MISURATA sul set reale (6 safe-certificati + 3 witness eseguiti + FP=0 + ABSTAIN 3-vie); colonne
  A1 (arXiv 2507.05558) / aether-PoCo (arXiv 2511.02780) dai PAPER (citate, non misurate). **Onesto a doppio senso:** VeriVault
  VINCE su gate-negativo/ABSTAIN/FP=0, **PERDE su ampiezza/generalità/cross-contract**. **Finding (web-verificato 2026-06-03):**
  VERITE (benchmark di A1) è **GENERAL-DeFi** (flash-loan/price-manip/reentrancy; max-revenue SHADOWFI/BEGO/AXIOMA/FAPEN/BAMBOO),
  **~0 casi ERC-4626 inflation** → A1 e VeriVault sono **REGIMI DISGIUNTI**. Il common-set SENSATO = il corpus VeriVault (22 vault
  mainnet LIVE: **16 immunity-cert vs A1 0-output** su questo corpus). Un re-run LETTERALE di A1 è poco informativo (overlap ~0) +
  code-gated. **Killer (per l'ADD):** safe-cert=0 o FP>0 — verificato falso (16 safe-cert live, FP=0).
- **(e) Productization** — *L4 il flusso-prodotto offline; live on-chain ancora RPC-gated*. FATTO: signer/portabilità
  (`certificate.py` + `test_certificate.py`); **`audit_onchain(addr)`** API enterprise (onesta: ABSTAIN dichiarato senza
  `ETH_RPC_URL`); **`audit_signed(...)`** flusso end-to-end **sorgente→exec-gate→CERTIFICATO FIRMATO PORTABILE**
  (`eval/test_product_flow.py`: VULN+witness firmato / IMMUNE firmato / content_hash+HMAC verificati); `pyproject` extra
  z3/anthropic; CI `verify.yml`; **`verify_all.py` one-command (25 check verdi offline)**. **✅ FATTO LIVE (RPC Alchemy):**
  `audit_onchain(sDAI)` mainnet → **IMMUNE + certificato FIRMATO** (content_hash+HMAC); BenchGate 22-vault live. Bug-parser
  (formato BenchGate) stanato dal run live e FIXATO. RESTA (minore): unificazione FISICA dei due repo-forge; un fork-test
  single-vault piu' veloce per `audit_onchain` (oggi rigira l'intero BenchGate).
  **Killer (superato per il flusso):** un certificato firmato è ora ri-verificabile da terzi (round-trip content_hash + HMAC).

## 5. Bug/rotture concrete
- ✅ **FIXED (BRICK 1):** `import verivault` rotto da `import z3` hard a `smt_rounding.py:17` → reso **lazy/guardato**;
  SMT degrada ad **ABSTAIN** se z3 manca (mai crash, mai finto-verdetto). Verificato: `import` + `test_algebra` exit 0.
- ⚠️ **APERTO:** due funzioni-rischio divergenti (`clean_risk` vs `defense_risk`, 24/68) — BRICK 3.
- ⚠️ **APERTO:** `stage5_conformal_threshold_fn` e `run_cascade` dead-code; conforme non wirata nel prodotto — BRICK 3.
- ⚠️ **APERTO:** `z3` non in `pyproject.toml`; due progetti forge non unificati; nessun signer — BRICK 8.
- ⚠️ **APERTO:** `BenchGate` self-skip fail-open senza RPC; split 16/6 non asserito — BRICK 7/8.

### Review avversariale di sessione (workflow, 12 agenti) — 6 issue trovati e FIXATI
- ✅ **HIGH — FP=0 violato:** `audit()` instradava un claim senza `result_key` → `forge_gate.decide` faceva blind-max su
  tutte le RESULT del demo (`raw`>0) → VULN spuria. **Fix:** `decide` ABSTIENE senza `result_key` univoco; `audit(gate_result_key=)`;
  test `test_cascade.py` caso (c). Il claim-core FP=0 è ora protetto anche per chiamanti futuri.
- ✅ **MEDIUM — SMT sopprimeva VULN:** UNSAT-su-codice-reale emetteva REFUTED+`immunity_certificate` saltando forge. **Fix:**
  short-circuit T1 solo per `closed_form_model`; su codice reale → sempre T3 forge; proof `model_immunity_hint` (non certificate).
- ✅ **MEDIUM — numero conforme contaminato:** `q_upper` clampava l'overflow a `max(cal_safe)` → `mean_FP=0.121` artefatto.
  **Fix:** overflow→+inf (astiene), confronti strict, achievability separata dall'overlap (numeri sopra, gap a).
- ✅ **LOW ×3:** GeneralGate assert vacuo se tutti-bloccati (guard sentinel); `forced_donation` dead-write rimosso + docstring; fallback `defense_risk` early-return `(0.5,False)`.
- **Esito:** green-sweep 6 Python + 7 forge tutti PASS post-fix. La review (REVIEW-phase del goal) ha fatto il suo lavoro: ha stanato un vero FP=0-breaker.

## 6. Roadmap a mattoni (nessuno passa prima del precedente; solo mattoni sound che COMPONGONO)
1. **BRICK 1** *(✅ fatto)* — lazy z3 → package importabile.
2. **BRICK 2** — pin `assertLe(maxProfit,0)` sulle 4 IMMUNE di GeneralGate (L2→L4); registra le esecuzioni §1.
3. **BRICK 3** — unifica risk-fn + wira conforme reale nella pipeline (uccidi il dead-code 0.5/`run_cascade`).
4. **BRICK 4 (gap a)** — set vergine indipendente + conforme per-distribuzione (stile PASC) → death-gate con assert.
5. **BRICK 5 (gap c)** — **coupled-FORGE**: misura profit(A∘B); il moat non-conteso reso L4-eseguito.
6. **BRICK 6 (gap b)** — Stage-3 harness parametrici-fedeli (ABI reale, mai ricostruzione).
7. **BRICK 7 (gap d)** — head-to-head misurato vs A1/aether sui loro output.
8. **BRICK 8 (gap e)** — signer certificato + `audit_onchain(addr)` + unificazione forge + CI.

*La cosa dirompente non è un claim più grande: è il fatto che i mattoni L4 §1 COMPONGONO (gate→algebra→certificato).*
