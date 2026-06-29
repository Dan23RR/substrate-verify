# Il fossato — VeriVault vs prior-art (onesto)

## Dove il campo è GIÀ affollato (NON reinventare)
- **Spina dorsale generale** `LLM→fatti-atomici→oracolo-deterministico/SMT→certificato`: **FormalJudge** (arXiv 2602.11136), **QWED-AI**, **NABAOS**, **Licensing Oracle** la stanno già spedendo (2026). Vendere "il Verification OS dell'economia AI" sarebbe over-claim.
- **Orchestratore-exploit end-to-end con fork-validation**: **A1** (62.96% VERITE, $9.33M validati), **aether**, **PoCo**, **V2E**, **EvoPoC**. F0 ne **eredita** la filosofia; non la supera in generale.
- **Invarianti ERC-4626 via fuzz/symbolic**: **crytic/properties**, **a16z/erc4626-tests**, **halmos**. (AGPL → reimplementate, non copiate.)

## Dove VeriVault resta DIFFERENZIATO (il fossato, triangolato da 3 fonti)
1. **Gate-NEGATIVO / certificato-immunità parametrico.** Tutti ottimizzano recall sui **positivi** (trova-l'exploit). Nessuno emette una **prova positiva di sicurezza** ("immune all'inflation per offset ≥ k, donazioni fino a k×deposito"). Il *fallire-a-violare-come-certificato* è originale. **Validato**: `forge/test/ImmunityCert.t.sol`.
2. **Verticale ERC-4626 share-inflation profondo.** I framework sono orizzontali; F0 è profondo su una classe con fatti tipizzati dedicati. La nicchia è dove anche A1/PoCo funzionano (single-contract) → l'edge NON è "exploit migliore" ma **gate-bidirezionale + calibrazione + costo**.
3. **Calibrazione conforme a 3 vie** `{VULN|SAFE|ABSTAIN+banda}`. I tool hanno ~11% di consistenza run-to-run e 38-51% di benigni flaggati; nessuno emette un **ABSTAIN calibrato** con copertura conforme garantita. È il differenziatore di **affidabilità-prodotto**.

## Il dolore è vivo
sDOLA Llamalend (2 Mar 2026, ~$240K via donation-attack); OpenZeppelin conferma "exchange rate manipulation risks" aperti. Non è un mercato morto.

## Onestà che non si nasconde (pitch-safe)
- Il salto W5 (AUC 0.92) è guidato da **fatti-LLM + scorer-deterministico**; il forge exec-gate è l'oracolo di **conferma separato** — non confondere le due metriche.
- Affidabile **solo sul single-contract inflation**; sul cross-contract crolla (come tutta la SOTA). Venderlo come "audit completo" sarebbe hype.
- **TAM stretto** (ERC-4626 inflation = una classe): rischio business, non tecnico. La generalizzazione del substrato si guadagna solo **dopo** che il cuneo supera il death-gate.
