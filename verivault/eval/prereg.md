# PRE-REGISTRAZIONE — Death-gate F0 (VeriVault)

**Timestamp: 2026-06-01.** Scritta PRIMA dei dati del death-gate, come richiesto dalla disciplina cardinale (anti-ASTRA).

## La riga da battere
`single-LLM recall@FP=0 = 0.636` — misurato in `research_substrate_capacity/exp/h2h_score_result.json` (17 contratti, round-1 head-to-head).

## L'esperimento
Misurare **recall@FP=0** della pipeline VeriVault completa (Stadio 1 fatti-LLM + Stadio 2 scorer-continuo + Stadio 4 gate-forge bidirezionale) su un dataset di **40–60 contratti share-accounting NON-VISTI**, con **soglia conforme CONGELATA** prima di vedere i dati.

## KILL-CONDITION (binaria)
Se la pipeline-fusa **NON supera 0.636 a FP=0** sul set non-visto → la tesi-fusione è **FALSIFICATA su questa nicchia** → **NO-GO**: si retrocede a "scanner + PoC come copilota d'audit", senza claim di superiorità, e l'intera tesi-substrato verification-native non passa il primo cancello.

## Secondo gate (decisivo per il VALORE, non solo per l'esistenza)
- **% di verdetti VULN** che arrivano con un **PoC che ESEGUE-E-VIOLA-INVARIANTE** su fork (non un claim) — deve essere alta.
- **% di SAFE con CERTIFICATO-IMMUNITÀ** parametrico valido — è il prodotto che nessuno vende; se ~0, il differenziatore-chiave cade.

## Anti-Schaeffer (obbligatorio)
Riportare l'**AUC dello scorer CONTINUO**, non solo la soglia binaria. Se l'effetto svanisce passando dal binario al continuo → artefatto → uccidi. (Gate già codificato: AUC<0.75 → texture.)

## Rigore (overfit-al-niche)
Il death-gate va corso su un dataset **indipendente** da quello su cui lo scorer W5 è stato sviluppato. W5 è tarato sull'inflation-niche (AUC 0.92 sugli analizzabili); il test vero è la **generalizzazione a contratti share-accounting non-visti** con la soglia congelata. Atteso onesto: degrado rispetto a 0.92; la domanda è se resta **> 0.636 a FP=0**.

## Risultati (da compilare DOPO il run)
- recall@FP=0 (analizzabili): __TBD__
- AUC continuo: __TBD__
- % VULN con PoC eseguito: __TBD__
- % SAFE con certificato-immunità: __TBD__
- **Verdetto: __GO / NO-GO__**
