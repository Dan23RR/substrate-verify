# VeriVault — Benchmark ESEGUIBILE del gate (death-gate, versione exec)

**Timestamp:** 2026-06-02 · **Domanda:** non "funziona?" ma "funziona *quanto*?" — copertura e verdetti dell'exec-gate
su un insieme ampio di vault ERC-4626 **reali** (sorgente upstream + deployati on-chain), a costo ~0 (RPC pubblico).

## Metodo (anti-fragilita, verification-native)
- **Attacco fedele unico**: chiama l'ABI REALE del vault (`deposit`/`redeem`/`balanceOf`) — nessuna reimplementazione → nessuna infedelta.
- **Verdetto 3-vie per soggetto**: `VULN` (profit eseguito > 0, con witness) · `IMMUNE` (nessuna donazione profitta entro il bound) · `ABSTAIN` (non eseguibile sul fork: token non finanziabile / deposito-guardato / 0-share). **Mai un finto-verdetto.**
- **Zero falsi-positivi per costruzione**: ogni `VULN` e un exploit ESEGUITO; ogni `IMMUNE` e una prova parametrica. Un `VULN` inatteso → verifica avversariale PRIMA di dichiararlo.
- **Due fonti**: (A) sorgenti upstream deployabili (harness `GeneralGate`); (B) indirizzi deployati on-chain via mainnet-fork (`BenchGate`).

## (A) Lato-SORGENTE — 5 forme su 4 librerie upstream reali (`GeneralGate.t.sol`)
| forma | libreria | difesa | verdetto eseguito |
|---|---|---|---|
| `totalAssets=balanceOf` | Solmate | nessuna | **VULN** (+25 token, witness D=V/2) |
| accounting interno | Solmate | internal | IMMUNE |
| virtual-shares | **Solady** | virtual +1 | IMMUNE |
| virtual-shares offset0 | **OZ** | virtual +1 | IMMUNE |
| virtual-shares offset6 | **OZ** | 10^6 | IMMUNE |

**Esito A:** 1 VULN (catturato), 4 IMMUNE (certificate). L'unica forma senza difesa e sfruttabile; tutte le difese reali respingono.
Nota verification-native: Solady/OZ-offset0 hanno **scorer-risk 0.85** (euristica cauta) ma il **gate prova IMMUNE** → la prova vince.

## (B) Lato-DEPLOYED — N vault reali su mainnet via fork (`BenchGate.t.sol`)
22 vault ERC-4626 **validati on-chain** (selettori `asset()`/`totalSupply()`): sDAI, sUSDS, sUSDe, sFRAX, scrvUSD, sDOLA,
sfrxETH, apxETH, wUSDM, Steakhouse/Gauntlet/Re7/Flagship (Morpho), Yearn V3 (USDC/WETH/DAI), Gearbox V3 (USDC/WETH), mevETH, wOETH, …

**SUMMARY (un fork, ~40s, RPC pubblico):  total=22 · IMMUNE=16 · VULN=0 · ABSTAIN=6**

| esito | n | vault |
|---|---|---|
| **IMMUNE** (certificato live, attacco eseguito e non-profittevole) | **16** | sdai, susds, sfrax, scrvusd, sdola, sfrxeth, apxeth, steakusdc, gauntusdc, yvusdc, yvweth, yvdai, dusdcv3, dwethv3, meveth, steakusdt |
| **VULN** (falsi-positivi) | **0** | — (disciplina FP=0 confermata dall'`assertEq(vuln,0)`) |
| **ABSTAIN** (non eseguibile, ragione dichiarata) | **6** | susde (redeem-guard/cooldown), wusdm·woeth (token non-finanziabile da `deal`), re7weth·flagshipeth·usdc_re7 (deposito-guardato: cap/coda Morpho) |

**Copertura on-chain: 16/22 = 73% certificati live provati, 0 falsi-positivi.** Gli ABSTAIN sono onesti (USDT gestito via call low-level;
i restanti hanno guardie reali di deposito/redeem o slot-balance non trovabile). Nota: USDT (`steakusdt`) richiese approve/transfer
non-standard → gestito; il gate NON cade su token non-conformi, li adjudica o si astiene.

## (C) Lato-DETECTOR — matrice di confusione su implementazioni ETICHETTATE reali (`LabeledBench.t.sol`)
7 implementazioni con label note, tutte su codice REALE (incluso **OZ ERC4626 v4.8.0 storicamente-vulnerabile**, pre-virtual-shares):

| implementazione | label | gate (eseguito) | esito |
|---|---|---|---|
| Solmate `balanceOf` | VULN | VULN (+25 token) | **TP** |
| **OZ v4.8** (no virtual-shares) | VULN | VULN (**+100 token = intero deposito vittima**) | **TP** |
| Solmate internal | SAFE | IMMUNE | TN |
| Solady virtual-shares | SAFE | IMMUNE | TN |
| OZ v5 offset 0 / 3 / 6 | SAFE | IMMUNE ×3 | TN |

**CONFUSION: TP=2 · TN=5 · FP=0 · FN=0 → recall=100% · precision=100%** (asserito da `assertEq(fp,0)`+`assertEq(fn,0)`).
Cattura codice upstream **storicamente-vulnerabile reale** per ESECUZIONE; certifica i safe; **zero falsi-verdetti**.

## (D) CATTURA su CODICE-INCIDENTE REALE — Compound v2 cToken (`CTokenGate.t.sol`)
Il gate SOUND (attacco-fedele-ABI, FP=0 per costruzione — **non** il path LLM-PoC) esegue l'attacco empty-market
sul **vero codice Compound v2** (port-0.8.10, `compound-finance/compound-protocol` riordinato): lo stesso codice
forkato da **Sonne ($20M, 2024), Hundred ($7.4M, 2023), Onyx ($2.1M, 2023)**. Mock minimi per Comptroller/IRM; tutto
il resto è il codice originale (`exchangeRateStoredInternal`, `mintFresh` `div_`, `getCashPrior=balanceOf`).

| target | classe | esito (eseguito) | witness |
|---|---|---|---|
| **Compound v2 cToken** (empty-market) | inflation exchangeRate | **VULN** — attaccante ruba **l'INTERO deposito-vittima (100 token)** | donazione D=1000 token; vittima riceve **0 cToken** |

**Perché conta:** è la **prima preda NON auto-scritta** catturata dal gate sound — il codice esatto di tre incidenti
multi-milionari reali, sfruttato per ESECUZIONE con witness-di-profitto. Uccide le due critiche più letali del prior-art
review: (#1) "l'unica vuln è auto-scritta" e (#2) "sui reali il gate fa FP=1 (path LLM-PoC fragile)". Qui: gate sound, FP=0, preda reale.
*Onestà di scope:* riproduzione del codice-incidente reale deployato localmente (mock Comptroller/IRM), **non** il replay
on-chain al blocco-pre-exploit (richiede RPC-archivio). È il codice reale + la classe reale, non l'istanza on-chain storica.

## Numero conclusivo combinato (A + B + C + D)
**27 soggetti reali** (5 sorgenti + 22 on-chain): l'exec-gate ha prodotto **20 certificati di immunita + 1 prova-di-vulnerabilita
(eseguita, +25 token) + 6 astensioni dichiarate**, con **0 falsi-verdetti**. Adjudica 21/27 = **78%**; si astiene sul 22% (sempre dichiarato).

## Significato (onesto)
Il numero conclusivo non e' "X% vuln scoperte" — i vault established sono safe by design, e non si fa hunting di exploit live.
E' **la COPERTURA + la DISCIPLINA di un verificatore eseguibile**: quante prove *vere* produce su contratti reali (immunita eseguita /
vuln eseguita), con **FP=0** e **ABSTAIN dichiarato** dove non puo concludere. La capacita di *catturare* la vuln e provata sul lato-A
(Solmate +25 token); il lato-B certifica l'immunita live. Non quanto promette: quanto **dimostra**, eseguendo.
