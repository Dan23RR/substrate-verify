# Disciplina-licenze — VeriVault (prodotto SaaS closed-source)

**Separazione netta e non-negoziabile:**
- **(a) CORE proprietario** = `verivault/` (Python nostro) + `forge/src` (Solidity nostro) + **solo** dipendenze permissive.
- **(b) Layer ESTERNO** = strumenti AGPL invocati come **binari CLI non-modificati via subprocess** (no linking, no vendoring, no patch). La mera invocazione non crea opera derivata → l'AGPL non contamina il core.

## Permissive — RIUSO-CODICE SICURO nel core
| Repo | Licenza | Uso |
|---|---|---|
| `foundry-rs/forge-std` | MIT/Apache-2.0 | Test/StdInvariant/Vm — riuso diretto nel `forge/` |
| `l33tdawg/aether` | MIT | pattern PoC-gen + compile-fix loop + fork-validation (Stadio 3/4) |
| `c5huracan/a1-agent-exploration` | MIT | scaffold dei 6-tool A1 (difensivo) |

## AGPL-3.0 — MAI nel core (solo subprocess o SPEC reimplementata)
| Repo | Uso consentito |
|---|---|
| `crytic/properties`, `a16z/erc4626-tests` | **solo SPEC**: le ~37 invarianti sono REIMPLEMENTATE in `forge/src/invariants/ERC4626Inflation.sol` (le invarianti non sono brevettabili) |
| `a16z/halmos`, `crytic/medusa` | CLI esterna non-modificata (vedi `external/README.md`) |
| `gustavo-grieco/quimera` | solo SPUNTO (loop trace), reimplementato |

## Nessuna licenza = TUTTI I DIRITTI RISERVATI (NON toccare il codice)
`advaitbd/smartguard` (idee architetturali OK, codice NO) · `ASSERT-KTH/PoCo-public` (core non rilasciato; trajectory come riferimento).

## Da decidere
La licenza di **VeriVault** stesso (`pyproject.toml: Proprietary TBD`). Opzioni: closed-source SaaS (core privato) con eventuale open-core dei componenti non-differenzianti.
