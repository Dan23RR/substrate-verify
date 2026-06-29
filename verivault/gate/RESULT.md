# Exec-gate su SORGENTE UPSTREAM REALE — Solmate ERC4626

**Timestamp:** 2026-06-02 · `forge test test/RealSolmateGate.t.sol -vv` · **2 PASS** · no RPC / no key / no banca
**Cosa:** l'exec-gate gira sul VERO Solmate (`vendor/solmate/`, scaricato da GitHub), **non** una reimplementazione.
**Licenza:** Solmate=AGPL → vive solo in `exp/` (EVAL), MAI nel core-prodotto (disciplina-licenze rispettata).

## Risultato (ogni numero dal forge)
| lato | vault (su Solmate reale) | esito | numero |
|---|---|---|---|
| **POSITIVO** | `totalAssets()=asset.balanceOf(this)` | **VULNERABLE** | maxProfit = 24.999e18 = **24% del deposito-vittima**, witness **D=50e18 (=V/2)** |
| **NEGATIVO** | `totalAssets()=` variabile interna | **IMMUNE** | maxProfit = **-1e18** (la donazione è inerte → persa dall'attaccante) |

Stesso identico Solmate base: il meccanismo-chiave (`totalAssets_type`, il segnale #1 dello scorer) **determina
da solo** vuln-vs-safe, **provato per ESECUZIONE**.

## Cosa ha rivelato (l'exec-gate guadagna il suo posto)
1. **`require(shares != 0, "ZERO_SHARES")`**: l'attacco-banale (vittima→0 share, D≥V) **revert** (1 caso bloccato). Il mio
   modello `RawVault` non aveva questa guardia → il furto reale NON è "ruba tutto" ma **ruba ~25% al confine di rounding s_v=1**.
   Solo eseguendo il sorgente vero si vede. (Conferma analitica: max profit ≈ V/(s+1)² → max a s=1 → V/4 = 25%, a D≈V/2.)
2. Il witness D=V/2 è **deterministico** (l'exec-gate lo restituisce per l'eventuale PoC on-chain).

## Limiti onesti
- Un solo contratto upstream (Solmate). Solady/OZ richiedono di vendorare le loro deps (assembly-heavy) — next.
- Self-contained: i contratti **deployed-only** (senza sorgente componibile) richiedono ancora il mainnet-fork (RPC).
- Il caso **Sherlock** (disputato in `../virgin_spotcheck.md`) richiede di mockare le sue dipendenze (yieldStrategy, premiums) — next.

## Ruolo nella pipeline
Trasforma il "flag" continuo dello scorer in un **verdetto eseguito** {VULN+witness | IMMUNE+certificato}. È il **lato-4**
(`ground`) della pipeline, ora su **codice reale** e non solo sui modelli — il fossato (gate negativo) dimostrato su upstream.

---

# AGGIORNAMENTO — HARNESS PARAMETRICO GENERALE (`test/GeneralGate.t.sol`)

**Timestamp:** 2026-06-02 · `forge test test/GeneralGate.t.sol` · **PASS** · 5 forme, 4 librerie upstream reali (Solmate/Solady/OZ).

**Idea (anti-fragilita):** UN solo attacco fedele che chiama l'**ABI REALE** del vault (`deposit`/`redeem`/`balanceOf`) —
nessuna reimplementazione → nessuna infedelta (la lezione del round-2). L'unica parte per-forma è il **deployer (2 righe)**;
l'attacco e lo sweep sono condivisi. Isolamento: deploy fresco per ogni trial (no snapshot fragili).

| forma (libreria reale) | meccanismo difesa | maxProfit attaccante | verdetto |
|---|---|---|---|
| Solmate `totalAssets=balanceOf` | nessuno | **+24.99e18** (witness D=50e18) | **VULN** |
| Solmate accounting interno | internal accounting | −1.00e18 | IMMUNE |
| Solady ERC4626 | virtual-shares (offset 0) | −0.50e18 | IMMUNE |
| OZ ERC4626 (offset 0) | virtual-shares (+1) | −0.50e18 | IMMUNE |
| OZ ERC4626 (offset 6) | virtual-shares (10^6) | −0.50e18 | IMMUNE |

**Generalita provata:** lo stesso attacco classifica VULN-vs-SAFE su 4 librerie e 3 meccanismi di difesa diversi
(internal-accounting, virtual-shares, offset-grande). L'unica forma profittevole e quella senza difesa; tutte le difese reali
fanno **PERDERE** l'attaccante (profit negativo).

## Loop end-to-end (`verivault/examples/realcode_demo.py`)
`audit_realcode(target.sol)` su tutte e 5 le forme: extract(LLM) → score → **GeneralGate (exec reale)** → certificato firmato.
**Punto chiave:** Solady e OZ-offset0 hanno **scorer-risk 0.85** (euristica cauta sull'offset-0), ma il **gate prova IMMUNE
per esecuzione** → il gate ha priorita (e' la prova, non l'euristica). È il cuore verification-native, dimostrato su codice reale.

## Limiti onesti (invariati)
- Le forme richiedono un **deployer** (costruttore) per contratto: i vault con dipendenze esterne pesanti (Morpho, comptroller)
  o **deployed-only** richiedono il mainnet-fork (RPC) — il deployer diventa `vm.createSelectFork` + indirizzo.
- L'attacco coperto e la classe **donation/first-depositor inflation**; altre classi (oracle, reentrancy) = altri harness.

---

# AGGIORNAMENTO — PATH DEPLOYED-ONLY via MAINNET-FORK (`test/ForkGate.t.sol`)

**Timestamp:** 2026-06-02 · fork mainnet via **RPC pubblico** (`ethereum.publicnode.com`, blocco ~25.228.690) · fork LOCALE, nessuna tx reale.
Il "deployer" diventa un **INDIRIZZO on-chain + `vm.createSelectFork`**: nessun sorgente/deps da ricostruire. Stesso attacco fedele
chiamato sull'ABI reale, contro lo **stato live** del contratto.

| vault reale (mainnet) | TVL live | esito | nota |
|---|---|---|---|
| **sDAI** `0x83F2…BEeA` | ~150M share / 177M DAI | **IMMUNE** (maxProfit −1e18, 4/4 eseguiti) | `totalAssets` = posizione pot-DSR, non `balanceOf` → donazione inerte |
| sUSDe `0x9D39…3497` | ~1.44B | **ABSTAIN** (deposito-guardato, 0/4) | guardia di deposito impedisce di eseguire l'attacco sul fork |
| sFRAX `0xA663…1c32` | ~56M | **ABSTAIN** (deposito-guardato, 0/4) | idem |

**Disciplina verification-native (il punto):** il gate emette **IMMUNE** solo dove l'attacco e' ESEGUIBILE e non profitta (sDAI);
dove non puo eseguire (guardie di deposito) **ABSTAIN** dichiarato — **mai un finto-verdetto**. PASS | REFUTED | ABSTAIN, su contratto LIVE.

**Cosa prova:** il gate opera su **indirizzi deployati reali** (non solo sorgente), senza RPC privato (endpoint pubblico).
Wiring in VeriVault = piccolo passo: `audit_onchain(address)` → `ForkGate` con `VAULT_ADDR` (il formato RESULT del fork e' piu ricco,
{IMMUNE|VULN|ABSTAIN}, va mappato nell'oracolo).

## Limiti onesti (fork)
- Il finanziamento dell'attaccante usa `deal()`: funziona su token standard (DAI) ma alcuni vault hanno **guardie di deposito**
  (cooldown/min/whitelist) che bloccano la simulazione → ABSTAIN onesto (non immune-finto). Aggirabile con whale-prank per token.
- Su vault ad alto-TVL l'inflation e' strutturalmente non-profittevole (seeded): il valore qui e' il **certificato di immunita live**,
  non la scoperta (per scoprire servono istanze fresche/empty, non hunting di exploit live).
