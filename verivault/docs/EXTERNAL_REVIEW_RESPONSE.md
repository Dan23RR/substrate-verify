# Risposta alla review esterna (2026-06-02)

Tre critiche acute e in gran parte **corrette**. Risposta con artefatti **riproducibili**, concedendo ciò che è vero.
Disciplina: niente difensività, niente overclaim.

---

## #1 — "Modello SMT altamente accoppiato e fragile" (CORRETTO, ora **delimitato nel codice**)

**Concesso:** `_profit_expr` modella solo due forme-chiuse (raw, OZ). Fee dinamiche pre-deposito, conversioni
multi-passo o accounting non-standard NON sono modellabili dal solver.

**Cosa è cambiato:** lo scope non è più solo un commento — è un **guard eseguibile**. `SmtRoundingOracle.supports()`
rileva le feature non-modellabili (`fee_bps`, `conversion_steps>1`, `hook_on_deposit`, accounting non-standard) e
`decide()` ritorna **ABSTAIN** invece di indovinare:
```
OZ standard      -> PASS       raw standard       -> REFUTED
FEE dinamica     -> ABSTAIN    multi-step         -> ABSTAIN    accounting non-standard -> ABSTAIN
```
**Il punto chiave:** l'SMT è solo il **tier-T1 veloce** per la sottoclasse modellabile. Il **MOAT è l'exec-gate forge**,
che è **form-AGNOSTICO** — chiama l'**ABI reale** del contratto (`deposit/redeem/convertToShares/exchangeRate`), non un
modello. Provato su **4 strutture di accounting diverse**: Solmate/Solady/OZ (`convertToShares`) + **Compound cToken**
(`exchangeRate`), tutte via ABI reale. Quindi la fragilità-SMT NON limita il prodotto: limita solo la *prova-su-continuo*,
non l'adjudicazione (che passa al forge). Verifica: `python -c "from verivault.oracles.smt_rounding import SmtRoundingOracle; ..."`.

---

## #2 — "Stadio 3 + fork su contratti reali = TODO/hardcoded" (PARZIALMENTE datato, in parte CONCESSO)

**Datato:** il fork su contratti reali NON è più un TODO. `exp/virgin/gate/ForkGate.t.sol` e `BenchGate.t.sol`
**forkano mainnet** (RPC pubblico) ed eseguono l'attacco-fedele su **22 indirizzi deployati reali** (sDAI, sUSDe,
Morpho, Yearn V3, Gearbox, …): **16 IMMUNE, 0 VULN, 6 ABSTAIN dichiarati, FP=0**. Riproducibile con `ETH_RPC_URL=... forge test`.
L'harness NON è per-contratto-hardcoded: è **parametrico** (un attacco via interfaccia `IVault` per qualsiasi ERC-4626).

**Concesso (genuinamente TODO):** lo **Stadio-3 LLM autonomo** (generare harness/exploit per contratti arbitrari o
interfacce nuove, senza un harness scritto) **non è costruito**. E concordo che è il collo di bottiglia dell'industria
(instabilità RPC, conflitti di stato, **ricostruzione infedele**). *Scelta di design esplicita:* VeriVault usa harness
**parametrici-fedeli** (chiamano l'ABI reale, zero ricostruzione) proprio per **evitare** la fragilità del-LLM-che-genera-PoC
— il nostro stesso round-2 h2h ha misurato FP=1 sul path LLM-PoC. Costo onesto: copriamo solo le classi-vuln con un harness
parametrico scritto (oggi **2**: inflation + rounding-direction), non un contratto arbitrario. Lo Stage-3 resta lavoro futuro,
non una capacità dichiarata.

---

## #3 — "Metriche autodichiarate / dataset TODO" (CORRETTO — ora **eseguibile**)

**Concesso:** `death_gate.py` era un runner che richiedeva un dataset esterno mai assemblato.

**Cosa è cambiato:** ora è **self-contained ed eseguibile** con dati reali bundlati:
```
python eval/death_gate.py          # 68 contratti reali, fatti LLM-estratti, in eval/data/labeled_facts.json
```
Risultato **riproducibile e ONESTO** (non scelto):
```
AUC (in-distribution) = 0.904        recall@FP=0 ranking = 0.515  (< 0.636 baseline)
PRE-REGISTRATA: recall@FP=0 > 0.636 AND AUC > 0.75  ->  NO-GO (in-distribution)
```
**Riportiamo il NO-GO.** L'AUC alta (0.904) NON implica recall@FP=0 alta (0.515): sono metriche diverse, e per la
condizione pre-registrata stretta **lo scorer-da-solo NON batte il baseline** → esattamente l'esito che `prereg.md`
prevedeva come falsificazione (retrocedi a copilota, niente claim di superiorità *per lo scorer*).

**Distinzione cruciale:** la critica accomuna "AUC 0.92" e "LabeledBench 100%", ma sono cose diverse:
- l'**AUC dello scorer** è in-distribution e ora misurata onestamente (0.904) → NO-GO sul gate stretto;
- il **LabeledBench 100%** NON è markdown: è un **`forge test` con assert in-codice** (`assertEq(fp,0)`, `assertEq(fn,0)`)
  su 7 impl reali (incl OZ-v4.8 storico) — **riproducibile**: `forge test --match-path test/LabeledBench.t.sol`. Idem
  `CTokenGate` (Compound reale catturato), `BenchGate` (22 mainnet). Questi sono il **moat verificabile**, non lo scorer.

---

## Sintesi onesta
| Critica | Stato dopo la risposta |
|---|---|
| SMT fragile | delimitato nel codice (`supports()`→ABSTAIN); forge form-agnostico è il moat |
| Stage-3 LLM autonomo | **genuinamente TODO** (conceduto); fork-su-reale invece è **fatto** e riproducibile |
| Metriche autodichiarate | death_gate **eseguibile** → NO-GO onesto per lo scorer; gli exec-gate sono `forge test`-verificabili |

La cosa che NON cambia: il valore reale è l'**exec-gate sound, form-agnostico, FP=0, riproducibile** — che cattura
codice-incidente reale (Compound) e certifica i safe. Lo scorer è un pre-filtro, e per il cancello stretto è **NO-GO**:
lo diciamo, non lo nascondiamo.
