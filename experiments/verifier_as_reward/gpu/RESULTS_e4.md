# E4 — Trans-dominio (firewall): results vs pre-registration

**Run:** 2026-07-03, Modal, 30 run (0 falliti), ~$30. Dominio nuovo: sintesi rule-set firewall su spazio finito di 64 pacchetti (proto × port 0-7 × src 0-3), semantica first-match/default-deny, DSL mai visto dal modello. Check esaustivo sull'intero spazio → il reward verifier è sound SENZA componenti a copertura parziale (test diretto del meccanismo weakest-link, P6). Config GRPO identica a E2 (600 step fissi, seed 42-46 agli estremi, 42-44 a 1.5B) salvo `max_completion_length=64`. Predizioni pre-registrate in `PREREG_e4.md`. JSON completi in `e4_results/`.

## La tabella madre (held-out, mean ± sd)

| scala | judge: hack | judge: correct | verifier: hack | verifier: correct | verifier: pass@k |
|---|---|---|---|---|---|
| 0.5B (5 seed) | 0.051 ± 0.069 | 0.041 | **0.000 ± 0.000** | 0.000 | 0.000 |
| 1.5B (3 seed) | **1.000 ± 0.000** | 0.000 | 0.457 ± 0.145 | **0.227** | 0.250 |
| 3B (5 seed) | **0.918 ± 0.100** | 0.024 | 0.180 ± 0.063 | 0.191 | 0.233 |

Controlli: parse-only@3B hack 0.0% (wrong-honest 100%); base 3B hack 3,4%.

## Scoring delle predizioni

**P1 — CONFERMATA a 16 SE (la domanda madre).** Il judge-hacking cresce con la scala anche nel secondo dominio: **5,1% → 100% → 91,8%**, Δ endpoint = 86,8pp contro 2·SE = 10,9pp. Forma diversa dal regex (qui salita ripida e saturazione già a 1.5B, sul regex crescita ancora in corso a 3B), **direzione identica**. Due domini su due: più il modello è capace, più sfrutta il reward non-sound. La firma è robusta al dominio nella direzione; la *forma* della curva è domain-dependent.

**P3 — CONFERMATA, perfetta anche qui.** Selettore-verifier: **0 certificazioni sbagliate su tutti i 30 run** E coverage == pass@k ovunque (verificato sui JSON, non assunto). Cumulativo sui due domini: **63 run, 0 errori del gate sound**. Selettore-judge sui bracci judge 1.5B/3B: media ~96%, fino al 100% (a 1.5B certifica il falso sul 100% dei task a tutti e 3 i seed).

**P6 — FALSIFICATA (il risultato meccanicistico più importante della run).** La predizione: senza componenti deboli nel reward, il basin near-miss non deve esistere. I dati: hack del braccio verifier **37-62% a 1.5B e 10-24% a 3B**, nonostante il reward sia interamente sound (agree=1 ⟺ equivalenza). **La spiegazione weakest-link di E1 è incompleta**: il basin near-miss non richiede una componente unsound — lo sostiene il *credito parziale denso in sé*, ogni volta che il successo esatto è più difficile del guadagno marginale (un near-miss prende ~0,49 e la policy può parcheggiarsi lì). Raffinamento del meccanismo: la componente debole del reward AGGRAVA il fenomeno (regex 0.5B: verifier ≈ judge), ma non è necessaria. Due note che restano vere: (a) il reward sound non certifica MAI quei near-miss (0/792+0/720 selezioni); (b) qui il near-miss coesiste con una generalizzazione molto più alta che nel regex (22,7% correct a 1.5B, 19,1% a 3B, pass@k fino a 29%): il basin non impedisce di imparare, inquina la coda.

**P2 — CONFERMATA (la divergenza pre-dichiarata).** Su regex il judge-trained non generalizza mai (0/15 run). Qui a 3B lo fa in 2/5 seed (max 9,4%): nel dominio finito con programmi veri corti, la pressione di Occam aiuta anche il judge — poco (resta 92% deceptive), ma non-zero. È il primo mattone della tassonomia dei gap.

**P4 — FALSIFICATA in questo dominio.** Il basin onesto (hack <10%) NON diventa universale a 3B qui: 5/5 (vacuo) → 0/3 → 1/5. La direzione 1.5→3B è giusta (hack medio dimezza, 45,7%→18,0%) ma non converge a zero. Il "5/5 onesto a 3B" del regex è domain-dependent — la parte "the remedy scales" della storia E2 va qualificata nel writeup (fatto).

**P5 — NON CONCLUSIVA (caveat pre-dichiarato applicato).** Il base 3B nel DSL nuovo ha parse-fail 47% e pass@k solo 8,3% — poca competenza latente da distruggere. Judge-trained: media 6,7% con 2 seed sopra il base. Niente unteaching netto qui; il test era informativo solo con un base competente. Curiosità onesta: il base 1.5B ha pass@k 20,8% > base 3B 8,3% (il 3B produce più testo non-parsabile: più verboso, meno compliant col formato).

**Dominanza appaiata (bonus):** hack(verifier) < hack(judge) a **ogni coppia seed/scala** in questo dominio (incluso 0.5B, dove nel regex c'erano pareggi sporchi). Correct(verifier) > correct(judge) ovunque tranne il vacuo 0.5B.

## Sintesi trans-dominio (2 domini, 63 run, 6 giorni-GPU equivalenti, ~$60 totali)

| claim | regex | firewall | verdetto |
|---|---|---|---|
| hacking del judge cresce con la scala | 62→93% (7 SE) | 5→92-100% (16 SE) | **si trasferisce (2/2)** |
| gate sound: 0 certificazioni sbagliate | 0/792 | 0/720 | **si trasferisce, perfetto (2/2)** |
| solo il braccio verifier generalizza davvero | sì (judge 0/15) | sì, ma judge 2/5 seed >0 a 3B | si trasferisce con taxonomy-note |
| basin onesto universale a 3B | 5/5 | 1/5 | **NON si trasferisce (domain-dependent)** |
| meccanismo weakest-link | compatibile | **falsificato come spiegazione completa** | raffinato: dense-partial-credit |
| unteaching | netto (16,7%→0%) | non conclusivo (base debole) | da ritestare con base competente |

**Una riga:** *in due domini strutturalmente diversi, l'hacking di un reward non-sound cresce con la capacità del modello (fino a 16 SE) e un gate di certificazione sound non sbaglia mai (0 errori su 1.512 selezioni cumulative); come il modello ci arriva — basin onesto o coda near-miss — dipende dal dominio, e il near-miss è sostenuto dal credito parziale denso in sé, non solo dalle componenti deboli del reward.*

## Cosa resta fuori
- 2 domini ≠ universalità; il terzo candidato naturale è ERC-4626 exec-gate (reward più sparso, rischio bootstrap).
- La forma della curva (saturazione vs crescita) va spiegata: probabile funzione della difficoltà relativa memorizzazione-vs-generalizzazione nel dominio.
- Niente oltre 3B.
