# Virgin-set spot-check — death-gate F0 (OOD, fresh real code)

**Timestamp:** 2026-06-01 · **Dato:** `research_substrate_capacity/exp/virgin/` (8 contratti reali scaricati fresh da GitHub)
**Estrazione:** workflow-agent W5-v2 (stesso LLM, **nessuna API-key usata**) · **Soglia:** congelata da W5 (dato vecchio→nuovo)

## Cosa è (e cosa NON è)
Spot-check di generalizzazione **out-of-distribution** su codice mai visto, fresco upstream. **NON** è il death-gate
finale: N piccolo (8), sbilanciato (5 SAFE / 3 VULN), canonico, **2 soli VULN analizzabili** → *suggestivo, non conclusivo*.
Complementa l'held-out in-distribution (`exp/death_gate_heldout.py`: ranking recall@FP=0 = 0.792 su 33 VULN).

## Set (label a base documentata/consenso, non auto-referenziale)
| # | contratto | label | esito estrazione |
|---|---|---|---|
| 01 | Solady ERC4626 | SAFE | virtual-shares default ON → defense 0.85 ✅ |
| 02 | OZ ERC4626 | SAFE | offset 10^0=1, mitigazione OZ → defense 0.60 ✅ |
| 03 | Solmate ERC4626 | VULN | `totalAssets()` astratto → `unknown` → **ABSTAIN** (onesto: base senza body) |
| 04 | Compound CErc20 | VULN | `getCashPrior()=balanceOf`, no virtual-share → defense 0.05 ✅ |
| 05 | Compound CToken | VULN | exchangeRate su cash esterno → defense 0.05 ✅ |
| 06 | MetaMorpho | SAFE | accounting **interno** (Morpho position) + offset → risk 0.04 ✅ |
| 07 | Yearn TokenizedStrategy | SAFE | `S.totalAssets` interno tracciato → risk 0.06 ✅ |
| 08 | Sherlock | SAFE(*) | **DISPUTATO**: il pipeline trova `balanceOf`-based + donation_vector → risk 0.90 |

## Risultati (ogni numero da `score_virgin.py` / `diagnose_virgin.py`)
- **Estrazione fatti: 8/8 corretta** rispetto al meccanismo reale (verificato sui `reasoning`).
- **Ranking recall@FP=0 = 1.000** (sia con sia senza Sherlock): i VULN (0.95) sopra tutti i SAFE (≤0.90). > 0.636 baseline. **[N=2 VULN]**
- **Soglia assoluta congelata-W5 (T=0.95): recall 0/2, FP 0/5.** Fallisce.
- **Sensibilità:** T∈[0.90,0.93] → recall 1.00, FP 0.00 (finestra perfetta). T=0.95 → tie → 0.00.

## Finding-1 (negativo, robusto): la soglia-assoluta-congelata NON si trasferisce OOD
T=0.95 è fissata da **un solo outlier W5**: `Venus_vUSDT_v2.sol` (label SAFE, defense 0.05, external) → risk 0.95.
Una soglia eps=0 è ostaggio del peggior SAFE-outlier di calibrazione. → **Il naïve "congela una soglia assoluta"
è FALSIFICATO come strategia di deploy.** Fix prescritto dall'architettura: **conformal per-distribuzione (stage5)**
o **exec-gate** per l'operating point. (Possibile data-quality issue in W5 su Venus: da auditare, NON risolvo unilateralmente.)

## Finding-2 (positivo): il SEGNALE generalizza
Separazione perfetta su codice fresco mai visto (ranking 1.0). L'estrattore-LLM legge la logica vera
(virtual-shares vs no, internal vs external accounting) anche su sorgenti upstream diversi dalle copie del benchmark.

## Finding-3 (il moat in azione): il caso Sherlock
Il pipeline ha **segnalato un donation-vector in un contratto che avevo etichettato SAFE di fretta** (dal nome-repo).
O è una scoperta reale o un near-FP — **solo l'exec-gate (eseguire l'attacco) disambigua**. È esattamente il ruolo
del gate-forge bidirezionale: PASS=vuln reale / REFUTED=safe. Senza esecuzione, lo scorer da solo non chiude il caso.

## Verdetto onesto
- Lo **strict pre-registered test** (soglia assoluta congelata) **non passa** (recall 0/2 al tie 0.95). Lo riporto per primo.
- La **diagnosi** mostra che è un artefatto di *trasferimento-soglia* (outlier Venus), non di segnale: ranking 1.0, finestra T perfetta.
- **N=2 VULN** → né il "passa-in-ranking" né le conclusioni sono statisticamente forti.

## Cosa serve per il death-gate DEFINITIVO
1. **Set vergine grande + bilanciato** (≥30-50, ≥15 VULN) con label indipendenti → unico modo di rendere il numero conclusivo.
2. **Exec-gate su contratti reali** (RPC) → disambigua i casi-Sherlock e fissa l'operating point eseguendo, non soglia.
3. **Conformal per-distribuzione** già in `stage5` → usarla al posto della soglia-assoluta-congelata (lezione di Finding-1).
