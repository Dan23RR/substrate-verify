# VeriVault

> **▶ PRODOTTO** — `pip install -e . && verivault demo` emette 2 certificati reali firmati (un **VULN** con exploit eseguito + un **IMMUNE** con prova). Positioning da compratore: **[PRODUCT.md](PRODUCT.md)** · certificati-demo: **[docs/demo_certs/](docs/demo_certs/)**. *(Il resto di questo README è la documentazione tecnica/research.)*
>
> ```bash
> verivault audit MyVault.sol --sign $SECRET --out cert.json   # qualsiasi vault ERC-4626 IVault — auto-wired, no config
> verivault audit --onchain 0x… --rpc $ETH_RPC_URL
> ```

**Verification-native audit per ERC-4626 share-inflation/rounding** — il primo mattone (**F0**) del substrato *verification-native* di **Verifier Labs**.

> Non emette risposte: emette **CLAIM che portano il proprio certificato**. Tre stati first-class:
> `PASS` (un oracolo deterministico conferma) · `REFUTED` (un controesempio uccide → **non esce**) · `ABSTAIN` (dichiarato, mai un finto-verdetto).

## La tesi (misurata, non slogan)
`VALORE = creatività-LLM (PROPONE) + grounding-deterministico (ORACOLO dispone) + cancello-di-falsificazione (REFUTED non esce) + COMPOSIZIONE.`
Il collo di bottiglia dell'era AI si sposta da *generare* (commodity, AI-slop, valid <5%) a **verificare**. VeriVault possiede il layer di verifica su una nicchia ad alta-conseguenza.

## Il fossato (3 cose che nessun competitor fa insieme)
1. **Gate NEGATIVO / certificato-immunità.** Non solo "ecco un exploit" (A1/aether/PoCo fanno solo questo) ma **prova parametrica di sicurezza**: sweep della donazione contro l'offset misurato → se nessuna donazione (fino a *k×* il deposito vittima) è profittevole, emetti un **certificato di immunità**. *Nessuno vende la prova-di-SAFE.*
2. **Verticale ERC-4626 profondo** (rounding-direction, virtual-offset, dead-shares, donation) con **fatti tipizzati** dedicati.
3. **Output calibrato a 3 vie** `{VULN+PoC | SAFE+certificato | ABSTAIN+banda-conforme}` — nessun prior-art emette un ABSTAIN calibrato.

## Stato (onesto)
> **STATO VERIFICATO 2026-06-03** — `python verify_all.py` → **ALL GREEN, 24 check** (16 Python + 8 forge). Mappa L0-L4
> onesta e aggiornata: [`docs/STATE_MAP.md`](docs/STATE_MAP.md) · cronaca: [`NIGHT_LEDGER.md`](NIGHT_LEDGER.md) · runbook
> enterprise turnkey: [`docs/ENTERPRISE_RUNBOOK.md`](docs/ENTERPRISE_RUNBOOK.md).
>
> **Correzioni di onestà** (alcune righe sotto sono datate/overclaim): lo *scorer* death-gate è **NO-GO stretto**
> in-distribution (pre-registrato e accettato → lo scorer è un **cost-router**, l'**exec-gate** è il gate sound; vedi sotto);
> il *tier T1 SMT/Z3* richiede `z3-solver` (extra OPZIONALE, degrada ad ABSTAIN se assente — il CORE non lo richiede); la
> *calibrazione conforme* è **SOTA integrato** (PASC), non invenzione; i *certificati firmati* sono **ora reali e testati**.

| Componente | Stato |
|---|---|
| Gate bidirezionale (modelli raw-vs-OZ) | ✅ **VALIDATO** — `forge test` passa: raw ruba 1e18 (positivo), OZ-offset immune (negativo). |
| Scorer deterministico su fatti (W5) | ✅ **MISURATO** — AUC 0.604(regex) → 0.776 → **0.920** (analizzabili). |
| **Tier T1 SMT/Z3** (`oracles/smt_rounding.py`) | ✅ **SOUND, testato** (`eval/test_smt_tier.py`, 63 casi): witness D\* reali, 0 exploit mancati. **Edge onesto = certificato-immunità-su-CONTINUO + witness** (il recall-gain sul grid è **falsificato**: 0 casi → il grid-9pt basta sui modelli standard). |
| **Cascata tiered** (`cascade.py`, T0→T1→T3) | ✅ **wirata + testata** end-to-end (safe→certificato-continuo cheap; vuln→witness→forge; low-risk→astieni). |
| **LOOP END-TO-END su CODICE REALE** (`audit_realcode`, `examples/realcode_demo.py`) | ✅ **CHIUSO su 5 forme** — sorgente → fatti-LLM (sub-agent) → rischio → **ESECUZIONE forge (harness generale)** → certificato firmato. 1 VULN (witness D\*=50e18, 25 token) + 4 IMMUNI. **Solady/OZ-offset0: scorer-risk 0.85 (euristica cauta) ma il gate prova IMMUNE → la prova vince** (cuore verification-native). |
| Kernel verification-native (Claim/Oracle/Certificate) | ✅ scaffold |
| Stadio 1 LLM-fact-extractor (W5-v2, AUC 0.92) | ✅ **dimostrato via sub-agent** (no key) nel loop reale; `extract_facts_llm` (SDK env-var) pronto per produzione. |
| Stadio 3 orchestratore (chaining 5 stadi) | ✅ **wirato** in `audit_realcode` (extract→score→propose→ground→calibrate); aether-style harness-gen automatico = next. |
| **Harness PARAMETRICO su CODICE REALE** (no RPC) | ✅ **VALIDATO** — `exp/virgin/gate/GeneralGate.t.sol`: UN attacco fedele (chiama l'ABI reale, no reimplementazione) classifica **5 forme su 4 librerie upstream** (Solmate/Solady/OZ): solo `balanceOf`-senza-difesa è VULN (furto 24%, witness D=V/2); internal-accounting, virtual-shares, offset-10^6 tutte IMMUNI (attaccante PERDE). Bidirezionale, per esecuzione. |
| Gate su CONTRATTI DEPLOYED-ONLY (mainnet-fork) | ✅ **DIMOSTRATO** — `exp/virgin/gate/ForkGate.t.sol` via **RPC pubblico**: sDAI live → certificato **IMMUNE** (donazione inerte); sUSDe/sFRAX → **ABSTAIN** onesto (deposito-guardato). "Deployer" = indirizzo on-chain + `createSelectFork`. Wiring `audit_onchain(addr)` = piccolo passo. |
| **BENCHMARK ESEGUIBILE su SCALA** (`exp/virgin/gate/BenchGate.t.sol` + `BENCHMARK.md`) | ✅ **MISURATO** — 22 vault ERC-4626 reali mainnet (validati on-chain), un fork ~40s: **16 IMMUNE (certificati live) · 0 VULN (FP=0) · 6 ABSTAIN dichiarati**. Combinato col lato-source (5 forme): **21/27 adjudicati (78%), 1 vuln catturata (+25 token), 0 falsi-verdetti.** |
| **CATTURA su CODICE-INCIDENTE REALE** (`CTokenGate.t.sol`) | ✅ **Compound v2 cToken empty-market** (codice esatto di **Sonne $20M / Hundred $7.4M / Onyx $2.1M**) catturato dal gate SOUND (FP=0), attaccante ruba **l'intero deposito-vittima**, witness D. **Prima preda NON auto-scritta.** |
| **Matrice di confusione detector** (`LabeledBench.t.sol`) | ✅ **recall 100% / precision 100%, FP=0/FN=0** su 7 impl reali, incl **OZ v4.8 storicamente-vulnerabile** (+100 token). |
| **Algebra composizione certificati** (`compose.py` + `algebra.py`) | ✅ JOIN/MEET (anello-debole) su verdetti SMT reali + **bound economici componibili** — il **gap non-conteso**; `Certificate.composed_from` popolato. **Falsificazione anti-ASTRA** (`eval/test_algebra.py`): weakest-link REGGE per link isolati ma si ROMPE sotto coupling (+80 vs −1 token) → l'algebra declassa onestamente a **triage/ABSTAIN**, mai falso-IMMUNE. Moat dichiarato col suo limite. |
| **2ª CLASSE-VULN: rounding-direction** (`RoundingGate.t.sol`) | ✅ stesso kernel/harness, sola variabile = direzione arrotondamento: up-rounding→**VULN** (0.5 token, witness x=1), down-rounding→IMMUNE. **Il framework è il prodotto, non l'euristica di 1 classe.** |
| Scope-naming del certificato | ✅ ogni cert d'immunità dichiara `scope_covers`/`scope_excludes` — overclaim chiuso (passività→asset). |
| Death-gate (scorer) su contratti NON-VISTI | ◐ **NO-GO stretto** in-dist (recall@FP=0=0.515<0.636, `eval/death_gate.py`) → scorer=**cost-router** (pre-registrato, accettato). Macchina offline-ready (`eval/test_death_gate_runner.py`); **GO@N=9 suggestivo** via W5-v2 (`eval/death_gate_w5v2.py`: recall@FP=0=1.0, margine +0.10). Resta: corpus terzo a scala (≥40-60). |
| **Stage-3 LLM-orchestratore AUTONOMO** (`eval/test_stage3.py`) | ✅ **ESEGUITO** — sub-agent legge sorgente **MAI-VISTA**, estrae fatti, **auto-genera harness FEDELE**; exec-gate dispone VULN+witness / IMMUNE, **FP=0** (l'LLM non scrive l'attacco → disciplina). Scope: vault IVault-compatibili. |
| **Estrattore-fatti DETERMINISTICO offline** (`verivault/extract_solidity.py`) | ✅ corretto sui 5 shape reali (`eval/test_extractor.py`) → prodotto **SELF-CONTAINED** (no API/no stub; LLM-W5v2 superiore sui casi semantici). |
| **Certificato FIRMATO portabile/contestabile** (`verivault/certificate.py`) | ✅ canonical-json + sha256 + tamper-detect + HMAC (`eval/test_certificate.py`); `audit_signed()` flusso end-to-end. |
| **Composizione UNIVERSALE — substrato dominio-agnostico** (`eval/test_substrate_agnostic.py`) | ✅ STESSO kernel su **3 domini** (DeFi · affidabilità · numerico); coupling super-additivo via oracolo-AMM **+78e21** (`OracleCoupledGate`) + correlazione **22×** (`test_correlated_failure`) → `protocol_verdict` declassa ad ABSTAIN. |
| **Head-to-head di capacità (misurato)** (`eval/head_to_head.py`) | ✅ vs A1 (arXiv 2507.05558) / aether-PoCo (2511.02780): VeriVault VINCE su {gate-negativo, ABSTAIN, FP=0}, **PERDE su {ampiezza, generalità, cross-contract}** (onesto). |
| `audit_onchain(addr)` + CI + one-command | ✅ API on-chain (ABSTAIN onesto senza RPC) + `.github/workflows/verify.yml` + `verify_all.py` (24 check). Live on-chain = `ETH_RPC_URL`. |

## Quickstart
```bash
# 1) il fossato, eseguibile e validato (gate bidirezionale):
cd forge && forge test --match-path test/ImmunityCert.t.sol -vv
# 2) la pipeline Python (fallback deterministico; cabla l'LLM-fact-fn per W5-v2):
python -c "import verivault as v; c=v.audit_immunity_demo(); print(c.verdict.status, c.verdict.proof)"
```

## Architettura (5 stadi, agnostica — cambia solo la libreria di oracoli)
`[1] extract` fatti tipizzati → `[2] score` rischio continuo (anti-Schaeffer) → `[3] propose` orchestratore-LLM → `[4] ground` **oracolo forge bidirezionale** → `[5] calibrate` output a 3 vie. Dettagli in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Il cancello (prima di costruire oltre)
Death-gate pre-registrato ([eval/prereg.md](eval/prereg.md)): battere **single-LLM recall@FP=0 = 0.636** su contratti **non-visti**, soglia congelata. Se non lo batte → **NO-GO**, retrocedi a copilota. *Nessun orizzonte passa il suo cancello prima del precedente.*

## Disciplina-licenze (prodotto)
CORE = solo MIT/Apache (forge-std) + codice nostro. Tool AGPL (medusa/halmos/crytic) **solo come subprocess non-modificati** → [docs/LICENSES.md](docs/LICENSES.md). Le invarianti ERC-4626 sono **reimplementate** (non copiate da crytic/a16z AGPL).

## Differenziazione vs prior-art
FormalJudge / A1 / QWED coprono la *spina dorsale generale* (LLM→fatti→oracolo). VeriVault **non la reinventa**: il valore è il **gate-negativo + il verticale + la calibrazione conforme**. Vedi [docs/MOAT.md](docs/MOAT.md).
