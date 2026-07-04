# PRE-REGISTRATION — E1 "soundness ladder" (+ E3 fold-in)

**Data:** 2026-07-02, scritta PRIMA di lanciare la run. Non modificare dopo il lancio; gli esiti si confrontano con questa pagina.

**Setup:** Qwen2.5-1.5B-Instruct, GRPO 600 step, stesso task/dati di `modal_grpo.py` (24 task held-out leak-checked, k_eval=16). 10 run di training + 1 eval del modello base, in parallelo su Modal A10G. Costo stimato: $10-14.

**Bracci:**
- `verifier` ×3 seed (42/43/44) — reward sound: probe-agreement (stringhe ≤7) + bonus equivalenza esatta
- `bounded6` / `bounded4` / `bounded2` ×1 seed — reward bounded-sound: agreement su TUTTE le stringhe ≤L + bonus se perfetto ≤L. Una regex giusta fino a L e sbagliata oltre massimizza il reward: il gap è il territorio non verificato
- `judge` ×3 seed — reward = accordo sugli esempi mostrati (il reward hackabile)
- `parse` ×1 seed — CONTROLLO: reward = 1 se la regex compila. Nessun segnale semantico
- `base` — CONTROLLO: modello non addestrato, zero pressione di ottimizzazione

**Metriche nuove:** esito fattorizzato per completion (parse_fail / wrong-but-honest / example-consistent-but-wrong = hack / equivalent), bounded-consistency a L=2/4/6, **first-divergence length** (lunghezza minima di stringa su cui candidato e target divergono, ≤9), e best-of-n per task (selettore = verifier sound con certify-or-abstain vs selettore = judge a esempi).

---

## Predizioni (falsificabili, scritte prima dei dati)

**P1 — Monotonia della ladder.** L'hack rate held-out (example-consistent-but-not-equivalent) decresce monotonicamente con la soundness del reward: `judge > bounded2 > bounded4 > bounded6 ≥ verifier`, con `verifier = 0%` su tutti e 3 i seed.
*Se fallisce (non-monotona):* la protezione è "a scatti", non graduata — risultato comunque riportabile, ma la frase "graded function of soundness" va ritirata.

**P2 — Il controllo (la predizione che può uccidere la Scoperta 1).** I bracci `parse` e `base` hanno hack rate **< 50% dell'hack rate medio del judge**. Cioè: l'hacking del judge è indotto dal *reward*, non dalla semplice capacità di fittare gli esempi del prompt.
*Se fallisce (parse/base ≈ judge):* la crescita 67→95.5% del sweep è in parte capacità sintattica ribattezzata "hacking" → **riscrivere §8 del writeup e RESULTS.md**, ridimensionare la claim prima di pubblicare. Questo esito vale più di una conferma.

**P3 — Gli errori migrano oltre il bound verificato.** Per i bracci `bounded_L`, tra gli output non-equivalenti e parse-validi, la first-divergence length mediana è **> L** (gli errori si concentrano oltre la regione verificata). Per il braccio `judge` la mediana è ≤ 3.
*Se regge:* "you get exactly what you verify: under RL, policy errors migrate past the verified bound" — il risultato nuovo, direttamente rilevante per il bounded model checking.
*Se fallisce:* gli errori non si localizzano al bordo → il gap bounded non viene sfruttato sistematicamente a questa scala; riportarlo.

**P4 — Exploit del territorio non verificato.** Per ogni braccio `bounded_L`, il tasso "bounded-consistent@L ma non equivalente" supera quello del braccio `verifier` di ≥ 10 punti percentuali.
*Se fallisce:* il reward bounded non induce hacking specifico al bound a questa scala/step-count.

**P5 — E3 (best-of-n), sanity + asimmetria.** Il selettore-verifier certifica solo output equivalenti (certified_wrong = 0 per costruzione; coverage = pass@k) e **si astiene** sul resto. Il selettore-judge sui bracci judge-trained certifica output sbagliati-ma-passanti in ≥ 25% dei task.
*Nota onesta:* metà di P5 è vera per costruzione; il numero informativo è il certified_wrong del judge e il confronto coverage.

**P6 — Stabilità sui seed.** Hack rate del judge entro ±15pp sui 3 seed; verifier 0% in 3/3.
*Se fallisce (varianza alta):* i numeri del sweep 0.5B→3B a seed singolo sono meno affidabili di quanto riportato → aggiungere caveat a §8.

---

## Cosa NON claimiamo comunque vada

- Nessuna "legge": un dominio solo. La promozione a legge richiede il secondo dominio (E4).
- Il plateau di generalizzazione (12.5% pass@k) resta non spiegato da questa run.
- Il TCB resta: il verificatore non verifica sé stesso (~300 righe + spec + Ed25519 fidati).
