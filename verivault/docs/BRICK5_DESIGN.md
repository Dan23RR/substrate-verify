# BRICK 5 — Coupled-FORGE: design + ipotesi di falsificazione (gap c)

> Obiettivo: rendere **eseguito (L4)** ciò che oggi in `algebra.py` è **modellato/hand-set (L1)** — il flag `monotone`
> e il coupling super-additivo `MEV(A∘B) > max(MEV(A),MEV(B))`. Disciplina: l'harness **MISURA** un numero; sia che
> il coupling esista sia che NON esista, è un risultato L4 (numero da uno script che gira). Niente assunzioni.

## Lo stato di partenza (cosa è già L4 e cosa no)
- `eval/test_algebra.py` eseguito (post-BRICK1): la **LOGICA** dell'algebra è coerente e asserita
  (coupling MEV=+80 → weakest-link ROTTA → `protocol_verdict`=ABSTAIN). **MA** il +80 viene da
  `composed_mev_oracle_leverage(V, pump=2.0, ltv=0.9) = ltv·V·pump − V`, un **modello a forma chiusa**, non un'esecuzione.
- `algebra.py`: il campo `EconomicBound.monotone` è un **input a mano**. Nessun forge lo deriva.

## Ipotesi di falsificazione (emersa dall'analisi di conservazione — da TESTARE)
Il modello `composed_mev_oracle_leverage` assume un pump del prezzo **flash-recuperabile** (l'attaccante gonfia,
prende a prestito, e **annulla** il gonfiaggio nello stesso tx — fedele per un **oracolo AMM-spot**, dove lo swap si
inverte). **Ma una donazione a un vault ERC-4626 è PERMANENTE e non-recuperabile.** Conseguenza per conservazione:

> Se B prezza il collaterale-A allo spot e ne prende **custodia**, e la manipolazione di A è una **donazione permanente**,
> allora l'asset iniettato dall'attaccante finisce nel valore del collaterale che B detiene → l'attaccante **finanzia**
> il prestito di B → `profit(A∘B) ≤ 0`. In più, le **virtual-shares** di A (che lo rendono individualmente IMMUNE)
> proteggono anche il depositante-B. → **Per la classe donation-inflation pura, il weakest-link potrebbe REGGERE empiricamente.**

**Se confermato**, è una falsificazione PARZIALE onesta del moat: la super-additività NON è una proprietà della
composizione di vault-immuni in generale; richiede una **dipendenza da price-oracle ESTERNO flash-manipolabile**
(AMM/spot recuperabile). Questo **re-scopa** il moat-composizione (e previene un overclaim), e indica la dipendenza
giusta da modellare. **Se invece** un harness fedele trova `profit(A∘B) > 0`, il coupling è confermato e `algebra.py`
declassa correttamente — moat empirico L4.

## Piano harness (misura, non assume) — `gate/test/CoupledGate.t.sol`
Tre misure, stesso pattern fedele degli altri gate (chiamano ABI reale, deploy fresco):
1. **`MEV(A)` da solo** — A = `OZVault` (virtual-shares, già misurato IMMUNE: maxProfit −497e15). Atteso ≤ 0.
2. **`MEV(B)` da solo** — B = mercato di prestito minimale che presta `asset` contro A-shares prezzate allo spot
   `A.convertToAssets`. Senza manipolazione del prezzo: atteso ≤ 0 (non si prende a prestito più del fair value).
3. **`MEV(A∘B)` composto** — DUE varianti del meccanismo di manipolazione, per separare le ipotesi:
   - **(3a) donation-permanente + custodia** (il caso che la conservazione predice ≤ 0): donate→borrow→abandon.
   - **(3b) oracle-leverage flash-recuperabile** (il caso del modello test_algebra): B prezza le partecipazioni
     **senza custodia** (account-value spot); attaccante flash-pompa, prende a prestito, **annulla** il pump (redeem),
     ripaga il flash, tiene il prestito. È il pattern reale degli oracle-manipulation hack.
4. **Assert che codifica il FINDING** (qualunque sia):
   - se `profit_3a ≤ 0` → `assertLe(...)` "weakest-link REGGE per donation-permanente+custodia" (falsificazione onesta).
   - se `profit_3b > 0` → `assertGt(...)` "coupling super-additivo CONFERMATO via oracle-leverage flash-recuperabile".
   - in entrambi: `assertGt(profit_3b, max(profit_A, profit_B))` quando 3b>0 = la definizione operativa di super-additività.

## Integrazione in `algebra.py` (chiudere il loop verification-native)
Sostituire il `monotone` hand-set con un verdetto **misurato**: una funzione che, dato l'output del CoupledGate,
imposta `monotone=False` SSE `profit(A∘B) > max(profit(A),profit(B))` **eseguito**. Allora `protocol_verdict`
declassa a **ABSTAIN** sul whole-protocol con evidenza eseguita (non modellata) — il certificato-composizione L4.

## Cosa lo UCCIDE (kill-condition del mattone)
- Se né 3a né 3b producono `profit(A∘B) > max(individuali)` con un attacco fedele → il coupling super-additivo è un
  **mito per questa classe** → ritira il claim "moat-composizione" e ri-scopa a "triage onesto via monotone-flag dichiarato".
- Se 3b profitta solo grazie a una **ricostruzione infedele** di B (non un mercato realistico) → non conta (FP per costruzione).

## Risultato MISURATO (2026-06-02, `gate/test/CoupledGate.t.sol`, PASS)
| misura | valore | nota |
|---|---|---|
| MEV(A) solo (donation-inflation) | −450e18 | A immune (OZ virtual-shares) ✓ |
| MEV(B) solo (fair borrow) | −10e18 | B fair, ltv<1 ✓ |
| MEV(A∘B) 3a — donazione + custodia | −110e18 | ≤ max(singoli) |
| MEV(A∘B) 3b — flash + custodia | −110e18 | flash NON ripagabile (lent≈0.9·(V+D)<D) → infeasible |

**FINDING (L4):** con una B **FEDELE (custodia)**, il weakest-link **REGGE** per la composizione *vault-interna*
donation-inflation — **nessuna super-additività**. L'ipotesi di conservazione è **confermata per esecuzione**.

**ARTEFATTO catturato (verifica avversariale — load-bearing):** una prima versione usava una B **senza custodia
né debito esigibile** (un *faucet*) e misurava **+990e18** "super-additività". È un **FP per costruzione**: la
fedeltà-di-B è load-bearing. Corretto → B con custodia → ≤0. *La disciplina "verifica avversariale di un VULN
inatteso PRIMA di dichiararlo" ha funzionato: il numero gonfiato non è uscito.*

**RE-SCOPE onesto del moat (c):** la super-additività NON è una proprietà della composizione di vault immuni;
richiede un **oracolo ESTERNO flash-recuperabile (AMM-swap)** — dipendenza **strutturale**. Quindi il flag
`monotone` di `algebra.py` deve codificare *"dipende da un oracolo esterno flash-manipolabile?"*, non il MEV vault-only.

## BRICK 5b (prossimo) — il caso POSITIVO + il wiring
1. `gate/test/OracleCoupledGate.t.sol`: mock-AMM constant-product come oracolo di B; attaccante flash-pompa lo
   swap, prende a prestito al prezzo gonfiato, **swap-back** (recupera), ripaga il flash → `profit(A∘B) > max(singoli)`
   **eseguito**. Conferma che il coupling esiste per la dipendenza-oracolo (assert `assertGt`).
2. `algebra.py`: `monotone` derivato dal verdetto CoupledGate/OracleCoupledGate (misurato), non hand-set; test che
   lega `profit(A∘B)>max` → `EconomicBound.monotone=False` → `protocol_verdict`=ABSTAIN (declassa, mai falso-IMMUNE).
