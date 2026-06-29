# benchmark/ — il dataset del death-gate (contratti NON-VISTI)

Il death-gate (`eval/death_gate.py`) richiede un set di **40–60 contratti share-accounting etichettati**,
**indipendente** da quello su cui lo scorer W5 è stato sviluppato (anti-overfit-al-niche).

## Formato
- `manifest.json` : `[{"id": "b01", "path": "/abs/path/Contract.sol"}, ...]` — **path NEUTRI** (il nome non
  deve rivelare l'etichetta: copia i `.sol` con nomi `bNN.sol`, come in `research_substrate_capacity/exp/h2h_prep.py`).
- `labels.json` : `{"b01": "VULNERABLE" | "SAFE", ...}` — tenuto SEPARATO, mai dato agli agenti/estrattori.

## Fonti consigliate (ground-truth ricco e gratis)
- **DeFiHackLabs** — incidenti reali di inflation/donation (con block/tx) → VULNERABLE confermati.
- **sDOLA Llamalend (2 Mar 2026, ~$240K)** e simili recenti → casi vivi.
- **OZ ERC4626 con/senza offset, Solady, Yearn V3, MetaMorpho** → mix di SAFE (con difesa) e hard-negatives.
- Fork **Compound-V2 / cToken / SushiBar**.

## TODO(Daniel)
1. Assemblare il set NON-VISTO (diverso dai 70 di `exp/w5v2_*`), neutralizzare i nomi.
2. Congelare la soglia conforme PRIMA di girare (`prereg.md`).
3. `python eval/death_gate.py benchmark/manifest.json benchmark/labels.json`.
