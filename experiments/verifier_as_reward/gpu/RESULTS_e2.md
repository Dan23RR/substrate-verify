# E2 — Multi-seed scale sweep: results vs pre-registration

**Run:** 2026-07-02, Modal (A10G per 0.5B/1.5B, A100-40GB per 3B), GRPO **600 step fissi a ogni scala** (de-confonde scala e compute; il vecchio sweep usava 300/600/900), 5 seed × {verifier, judge} per scala + base per scala. Al 1.5B i seed 42-44 sono i run E1 (config identica). 27 run nuovi + 6 riusati, **0 falliti**, costo ~$20-25. Predizioni pre-registrate in `PREREG_e2.md` prima del lancio. JSON completi (con completions classificate) in `e2_results/`.

## La tabella madre (held-out, mean ± sd su 5 seed)

| scala | judge: hack | judge: correct | verifier: hack | verifier: correct | verifier: pass@k | basin onesto (v) |
|---|---|---|---|---|---|---|
| 0.5B | **0.623 ± 0.002** | 0.000 | 0.500 ± 0.280 | 0.000 | 0.000 | 1/5 |
| 1.5B | 0.667 ± 0.175 | 0.000 | 0.215 ± 0.238 | 0.073 | 0.100 | 2/5 |
| 3B | **0.933 ± 0.051** | 0.000 | **0.027 ± 0.026** | **0.141** | 0.158 | **5/5** |

Base (mai addestrato) per scala: hack 0.3% / 0.0% / 0.0%; parse-ok 32.8% / 43.5% / 98.7%; pass@k 0 / 0 / 16.7%.

## Scoring delle predizioni

**P1 — CONFERMATA (la domanda madre).** Il judge-hacking cresce con la scala: Δ(3B−0.5B) = **31.0pp** contro 2·SE = 4.6pp; ordinamento delle medie 0.623 ≤ 0.667 ≤ 0.933 monotono. **Il trend che E1 aveva onestamente declassato a "osservazione single-seed" è ora ri-stabilito con 5 seed per punto e compute fisso.** Nota di struttura: la varianza è minima agli estremi (sd 0.002 a 0.5B, 0.051 a 3B) e massima nel mezzo (sd 0.175 a 1.5B) — il regime di transizione è dove vivono i seed bimodali di E1.

**P2 — PARZIALE.** Dominanza appaiata hack(verifier) < hack(judge) a **ogni seed** per 1.5B e 3B (10/10). A 0.5B fallisce in 4/5 coppie, ma per pareggi al margine (0.625 vs 0.620-0.625): a quella scala il modello non riesce mai a guadagnare il bonus di equivalenza, quindi il termine denso domina e il braccio verifier collassa nello stesso attrattore near-miss del judge. Coerente con la regola dell'anello-più-debole di E1: **sotto la soglia di capacità, il reward sound composito non compra alcun vantaggio comportamentale.**

**P3 — CONFERMATA, perfetta.** Selettore-verifier: **0 certificazioni sbagliate su tutti i 33 run** (792 certificazioni task-level, incluse quelle sui modelli judge-trained al 98.7% di inganno). Selettore-judge sui bracci judge: media 75.8%, fino al 100%. Seed-independent, scale-independent.

**P4 — CONFERMATA (era la predizione debole, è diventata il secondo titolo).** Frequenza del basin onesto del braccio verifier: **1/5 → 2/5 → 5/5**. A 3B il braccio verifier è onesto a OGNI seed (hack max 6.2%). Combinata con P1: **la scala è un amplificatore bidirezionale — rende il gaming del reward non-sound più aggressivo (62→93%) E rende l'onestà sotto il reward sound l'attrattore universale (20%→100% dei seed).** La bimodalità di E1 era il regime di transizione, non un difetto permanente del reward composito.

**P5 — CONFERMATA.** Capacità del base monotona: parse-ok 32.8→43.5→98.7%, example-agreement medio 0.20→0.28→0.62, pass@k 0→0→16.7%. Il framing "hacking vs capacità" ha il suo asse x.

## La scoperta non pre-registrata (riportata perché scomoda)

**Il reward non-sound non si limita a non insegnare: dis-insegna.** Il base 3B, campionato 16 volte con il verificatore come selettore, risolve **16.7%** dei task held-out (con 0 certificazioni sbagliate). Dopo il training contro il judge: **0% a tutti e 5 i seed**, sostituito da 93.3% di output ingannevoli. Il training contro il judge distrugge una competenza latente che il modello base già aveva.

**E il rovescio onesto sul valore del training col verificatore a 3B:** la coverage del verifier-trained (pass@k medio 15.8%) è ~uguale a quella del base filtrato (16.7%). Il valore aggiunto del training a questa scala non è coverage ma **affidabilità per-campione**: correttezza per-completion 14.1% vs 4.2% del base (~3.4×), cioè servono ~3× meno campioni per soluzione certificata. Diciamo questo chiaramente invece di gonfiare: a 3B su questo task, "filtra il base" e "traina col verifier + filtra" coprono gli stessi task; il training paga in efficienza, non in copertura. (A 1.5B invece il filtro sul base recupera 0%: lì il training era necessario anche per la coverage.)

## Sintesi in una riga

*A compute fisso e con barre d'errore: più il modello è capace, più aggressivamente sfrutta un reward non-sound (62.3%→93.3%) e più stabilmente si allinea sotto un reward sound (basin onesto 20%→100% dei seed); il gate di certificazione sound non sbaglia mai (0/792), qualunque cosa il modello abbia imparato; e il reward non-sound cancella perfino la competenza latente del base (16.7%→0%).*

## Cosa resta fuori (onestà di scopo)

- Un dominio solo (regex). La promozione a "legge" resta gated dal trans-dominio (E4).
- Estrapolazione oltre 3B: non fatta. E2b (7B, 3 seed) ora ha senso dato che il trend è reale; decisione a Daniel (~$20-25).
- Il plateau di generalizzazione (~12-16% pass@k a 1.5B/3B) resta non spiegato; ora sappiamo che a 3B è condiviso dal base filtrato → è un tetto del task/dati, non del metodo di training.
