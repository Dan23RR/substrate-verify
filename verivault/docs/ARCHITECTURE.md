# Architettura — VeriVault

Loop **verification-native** a 5 stadi (`decompose → ground → refute-gate → compose`). Identico in ogni dominio; agnostico per scelta-di-oracoli.

```
 .sol (+ opz. address+block)
        │
 [1] EXTRACT  stage1_extract.py     fatti tipizzati: totalAssets_type (internal=immune / balanceOf=manipolabile),
        │                            effective_offset, dead_shares, donation_vector, defense_strength
        │                            (A) deterministico auto_jacobian  +  (B) LLM-fact-extractor [W5-v2, AUC 0.92]
 [2] SCORE    stage2_score.py       rischio CONTINUO in [0,1] (anti-Schaeffer); 'unknown' -> ASTIENE
        │
 [3] PROPOSE  (orchestratore LLM)   costruisce Claim + harness forge; loop auto-riparazione  [TODO: aether MIT]
        │
 [4] GROUND   oracles/forge_gate.py  GATE BIDIREZIONALE su forge:
        │        POSITIVO  -> PoC gira su stato reale e viola invariante  -> Verdict PASS (+ controesempio = PoC)
        │        NEGATIVO  -> sweep donazione vs offset; max-profit<=0     -> Verdict PASS (+ proof = CERTIFICATO-IMMUNITA)
        │        (compile-fail / proxy senza impl)                        -> Verdict ABSTAIN (tipizzato)
 [5] CALIBRATE stage5_calibrate.py  output a 3 vie {VULN+PoC | SAFE+cert | ABSTAIN+banda-conforme}
        │
 Certificate (firmato, portabile, contestabile). REFUTED NON esce (refute-gate).
```

## Composizione
Un Claim composto eredita il certificato **più debole** della catena (`Certificate.composed_from`). La "singolarità" = mattoni-L4 (gate + certificato) che si compongono — uno alla volta, ognuno col suo death-gate.

## Stadio 4 su contratti REALI (TODO)
Oggi il gate gira su **modelli** raw-vs-OZ (validati). Per contratti reali: `IVault` + `vm.createSelectFork(rpc, block)` per deployare lo stato reale, l'orchestratore (Stadio 3) genera il PoC, `forge_gate` lo esegue. Richiede: RPC per chain (Ethereum/Avalanche/BSC…), il pattern fork-validation di `aether` (MIT). Per i proxy senza implementazione → ABSTAIN (fuori-scope source-only).

## Oracoli (agnostico)
`Oracle.decide(Claim) -> Verdict`. Registrati in `OracleRegistry`. Aggiungere un dominio = aggiungere oracoli (es. `smt` per rounding via Z3, `medusa` come subprocess per fuzzing stateful). Mai un secondo modello probabilistico (NLI) come oracolo: non dispone binariamente.
