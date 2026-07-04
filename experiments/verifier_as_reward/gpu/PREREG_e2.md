# PRE-REGISTRATION — E2 "multi-seed scale sweep"

**Data:** 2026-07-02, scritta PRIMA di lanciare la run. Non modificare dopo il lancio.

**Domanda.** Il claim "il reward-hacking sotto il judge cresce con la scala" (single-seed sweep: 67→62.5→95.5%) è un trend reale o rumore di seed? E1 ha mostrato spread ~47pp su 3 seed a scala fissa: senza questo test, il claim non è pubblicabile.

**Design (corretto rispetto al vecchio sweep):**
- Scale: Qwen2.5 **0.5B / 1.5B / 3B**. Il punto 7B è rimandato a un eventuale E2b SOLO se il trend 0.5→3B risulta significativo (logica sequenziale: non spendere sul punto costoso prima di sapere se il trend esiste).
- **Step FISSI a 600 per tutte le scale** (il vecchio sweep usava 300/600/900, confondendo scala e compute di ottimizzazione — deviazione documentata: i numeri 0.5B/3B non saranno direttamente confrontabili col vecchio sweep).
- **5 seed per braccio per scala** (42-46), bracci `verifier` (composito denso+equivalenza, identico a E1) e `judge` (esempi). Al 1.5B si riusano i 6 run di E1 (config identica: stesso modello, step, dati, seed 42-44) + 2 seed nuovi per braccio.
- `base` (non addestrato) valutato a ogni scala: controllo hack + asse-capacità (parse rate, mean example-agreement, pass@k del base).
- Stessi dati di E1 (76 prompt train, 24 task held-out leak-checked), k_eval=16, stesse metriche fattorizzate + best-of-n. Completions classificate salvate nei JSON per rianalisi.
- Totale: 27 container (11 @0.5B su A10G, 5 @1.5B su A10G, 11 @3B su A100-40GB). Costo stimato $20-30, wall-clock ~1-2h in parallelo.

---

## Predizioni (falsificabili, scritte prima dei dati)

**P1 — Il trend di scala (la domanda madre).** mean hack del braccio judge a 3B > a 0.5B, con Δ(3B−0.5B) > 2·SE_pooled (SE dai 5 seed per punto). In più, ordinamento delle medie 0.5B ≤ 1.5B ≤ 3B.
*Se fallisce:* il claim "cresce con la scala" viene ritirato e si pubblica il negativo onesto: "a ≤3B il reward-hacking indotto dal judge è alto a ogni scala ma la crescita non è separabile dal rumore di seed". È un esito pubblicabile e utile.

**P2 — Dominanza appaiata (il claim comparativo).** A ogni coppia (seed, scala): hack(verifier) < hack(judge) E correct(verifier) ≥ correct(judge), con correct(judge)=0 ovunque e correct(verifier)>0 in almeno 1 seed per scala ≥1.5B.
*Se fallisce (qualche seed con verifier ≥ judge in hack):* il vantaggio comportamentale del reward sound non è nemmeno direzionale a quella scala — da riportare così.

**P3 — Certificazione (sanity + asimmetria, seed/scale-independent).** Selettore-verifier: 0 certificazioni sbagliate su TUTTI i run a TUTTE le scale (25 run × 24 task). Selettore-judge: media wrong-cert ≥ 25% sui bracci judge-trained.
*Se fallisce la prima metà:* bug nel kernel di eval — più interessante del risultato stesso, da investigare prima di ogni altra cosa.

**P4 — Frequenza del basin onesto (esplorativa, predizione debole).** Frazione di seed del braccio verifier con hack <10% ("basin onesto"): a 1.5B è 1/3 da E1. Predizione debole: non-decrescente con la scala (il 3B single-seed era onesto). Nessuna conseguenza forte in caso di smentita: è mappatura del fenomeno bimodale scoperto in E1.

**P5 — Asse capacità (sanity del framing).** La capacità del base sul task (parse rate e/o mean example-agreement) cresce monotonicamente 0.5B→3B. Se non cresce, il framing "hacking vs capacità" perde l'asse x e va riformulato in "hacking vs parametri".

## Cosa NON claimiamo comunque vada
- Nessuna estrapolazione oltre 3B senza E2b.
- Il plateau di generalizzazione resta fuori scopo.
- Un dominio solo: la promozione a "legge" resta gated da E4 (trans-dominio).
