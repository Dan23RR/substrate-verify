# Delega verificabile (sumcheck / IP per #SAT)

> **Tier: PROVEN-soundness / NON-paradigma.** Verdetto avversariale (3 attaccanti, alta confidenza):
> `REAL_BUT_NOT_PARADIGM`. Tenuto come **exhibit di falsificazione chiuso** + strumento didattico/eval, MAI
> come claim di prodotto o direzione-Nobel.

## Cosa è (gated VERDE, `gate_delegation.py`)

Un **verificatore TINY e DEBOLE** che verifica un conteggio #SAT (un problema #P) interagendo con un **prover
POTENTE ma NON FIDATO**, con soundness **informazione-teorica**:

- Verificatore tiny **strutturale** (AST-confermato): 1 sola valutazione dell'aritmetizzazione, nessun loop su
  2^n, nessun solver. ~80 righe auditabili.
- **Soundness MISURATA**: prover bugiardi (conteggio falso / coefficiente manomesso / garbage) → **false-accept
  = 0/80 seed** ciascuno. La soundness viene dal protocollo (Schwartz-Zippel su F_{2^61−1}, error ~deg/p), non
  da un punteggio imparato.
- **Gap di delega**: a n=16, il prover fa ~352.000 valutazioni (#P work, >2^16); il verificatore ne fa **1**.
  Verifica un conteggio che non potrebbe mai calcolare, e becca ogni menzogna.

## Perché è l'unico sopravvissuto ai due trap (e perché comunque non è paradigma)

È **l'unico candidato della sessione** che sfugge a entrambi i trap che hanno ucciso tutto il resto:
- **TRAP-LEAN**: il verificatore tiny *non possiede* la regione (è debole); la fiducia nasce dalla **delega**,
  non dal ri-decidere. Un solver/enumeratore sotto lo stesso budget esplode.
- **TRAP-REWARD**: la soundness è dal **protocollo**, non da un punteggio hackerabile.

**Ma non è un paradigma**, e il verdetto lo stabilisce senza appello:
1. **Teoria di 35 anni fa**: LFKN sumcheck (1990), Shamir IP=PSPACE (1990), GKR doubly-efficient IP (2008).
   "Verificatore tiny controlla lavoro #P di un prover non fidato" è la proprietà *da manuale* del sumcheck —
   un confine **noto ri-mostrato**, non nuovo.
2. **L'AI è incidentale**: qualsiasi prover (script, umano, LLM) esegue lo stesso identico calcolo #P. Un LLM
   nel ruolo non aggiunge capacità; la soundness è indifferente a chi sia il prover.
3. **L'angolo "verifica di agenti AI non fidati" è già occupato**: zkAgent (eprint 2026/199), Verde (2025),
   Neural Interactive Proofs (NeurIPS 2024), doubly-efficient debate (Brown-Cohen 2023).
4. **Lower bound formale**: la PAC-verification dice che un verificatore limitato *non guadagna capacità* da un
   prover non fidato in regimi ampi — un muro teorico a quanto l'AI possa essere "essenziale" qui.

## Cosa lo renderebbe paradigma (e perché non è raggiungibile come tale)

Servirebbe un'istanza **AI-ESSENZIALE**: un agente di frontiera che *scopre* una strategia di prova / un
certificato succinto che **nessun programma fattibile** produce, verificato da un checker tiny su una
computazione che *davvero* andava delegata — dove conta la **capacità** del prover, non il suo compute. L'artefatto
attuale è l'opposto (ogni prover fa la stessa somma brute-force). Ed è comunque già una linea di ricerca altrui
(Neural Interactive Proofs, prover-verifier games) → sarebbe inseguimento, non primato.

## File
`sumcheck.py` (verificatore tiny + prover onesto/avversari) · `gate_delegation.py` (D1–D5, exit 0/1) ·
`_smoke_sumcheck.py` (640 verifiche, soundness rapida).

## Prior-art (da non ri-litigare)
LFKN 1990 · Shamir IP=PSPACE 1990 · GKR 2008 · verifiable computation (Goldwasser-Kalai-Rothblum) ·
zkAgent 2026 · Verde 2025 · Neural Interactive Proofs NeurIPS 2024 · doubly-efficient debate 2023.
