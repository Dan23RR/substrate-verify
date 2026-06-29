# substrate_core/rlvr — Substrate-RLVR / "L'Organismo Verificato"

> Addestrare Qwen-2.5-Coder-1.5B **contro l'oracolo sound `regex_equiv`**, con disciplina di falsificazione.
> Tutto il lato-dati e' qui (CPU/no-GPU); il fine-tuning gira su Colab/RunPod. `substrate_core` (il fossato) NON si tocca.

## La tesi, RIDIMENSIONATA con onesta' (review avversariale 2026-06-07, ogni claim su codice eseguito)

Un judge-panel (3 giudici) + 3 red-team, ancorati a esecuzioni reali, hanno **provato a rompere** il piano. Esito:
nessuno ha ucciso la tesi, **tutti l'hanno costretta a ridimensionarsi**. Cosa e' rimasto vero e cosa e' caduto:

| Claim dell'handoff | Verdetto |
|---|---|
| "Il verificatore-come-reward e' il vantaggio" | **Non e' novita'** (RLVR/DeepSeek-R1/Tulu-3 lo fanno gia') |
| "Reward sound ⇒ niente reward-hacking" | **FALSO**: l'identita' `R'=R` satura il CONFIRMED (riprodotto). La soundness copre *"e' equivalente?"* (~10%), non *"e' un buon rewrite?"* (~90%) |
| "L'intelligenza si somma via cert-algebra" | **Category-error**: `compose_and` compone *verdetti*, non *capacita'*. Ritirato dal training |
| "self-play / distill-merge" (pilastri 5-6) | **Vaporware** (nessun file): aspirazione, non scope |
| Fix proposto `|DFA(R')| < |DFA(R)|` | **Insoddisfacibile**: il DFA minimo e' un *invariante di linguaggio* (`a{10}` e `aaaaaaaaaa` = 12 stati). La semplificazione vive solo a livello sintattico/AST → `tier=empirical` |

**Il fossato onesto, tier-typed:** (1) [CONFERMATO] oracolo completo+sound+decidibile → reward incorruttibile;
(2) [ASPIRAZIONALE, ~2 bit/REFUTED, non-testato] witness-conditioned learning; (3) [PRODOTTO] **tier-head calibrato**
(proven|empirical|abstain, falso-proven = peccato cardinale). Il valore reale e' **calibrazione + gradiente-da-controesempio**,
non "capacita' regex sovrumana".

## I moduli (tutti no-GPU, tutti gated)

| File | Ruolo | Crepa che chiude |
|---|---|---|
| `oracle.py` | seam unico verso `regex_equiv` (import esplicito; path verdetto corretto; witness `''` reale) | — |
| `quality.py` | proxy di semplicita' = `ast_nodes` (parse-tree greenery). **EMPIRICAL, mai proven** | spiega perche' il DFA non funziona |
| `reward.py` | reward 3-stadi: G1 sound (`CONFIRMED@proven`) · G2 anti-identita' · G3 `ast_nodes` strettamente minore | **#1** saturazione-identita' |
| `factory.py` | fabbrica-dati 3 canali (A proven-semplice self-checked · B REFUTED+witness · C iniezione ABSTAIN); train/holdout a **regole disgiunte** | **#3** (genera, non filtra) · **#5** (anti-overfit) |
| `pregate.py` | **esperimento #0**: `pass@k` del base; se `pass@1<5%` → progetto falsificato a costo zero | **#3** (nulla da amplificare) |
| `dpo_builder.py` | coppie DPO con la `distinguishing_string` iniettata nel rejected | **#4** (consuma il "perche'") |
| `evaluator.py` | solve-rate-genuino · **falsi-proven==0 (vincolo duro)** · ECE (solo con `<conf>` emessa) · risk-coverage | — |
| `protocol.py` | confronto pre-registrato A-controllo vs B-witness-DPO, hash congelato, soglia morte 5pp | anti p-hacking |
| `train_qlora_colab.py` | **lo lanci TU** su Colab (QLoRA 4-bit, 3 bracket A/B_plain/B_witness). Validato solo *staticamente* in locale | — |
| `compare.py` | legge gli `eval_report.json` dei bracket → **effetto-witness puro** (B_witness−B_plain) vs soglia 5pp | cabla il cancello §8 |

## Riprodurre il cancello (no-GPU)

```bash
python -m substrate_core.rlvr.verify_rlvr      # -> "RLVR ALL GREEN" (pytest + lint-statico + audit fabbrica)
python -m substrate_core.rlvr.factory --n 400  # genera data/train.jsonl + data/holdout.jsonl
python -m substrate_core.rlvr.pregate          # genera l'holdout dell'esperimento #0
python -m substrate_core.rlvr.protocol         # stampa l'hash congelato del protocollo
```

## Cosa lanci TU su Colab/RunPod (GPU)

Setup (una cella): `pip install "trl>=0.12" "transformers>=4.45" peft datasets bitsandbytes accelerate`, clona il
repo, monta Drive. `HF_TOKEN` da **Colab Secrets/userdata** (mai in chat). Poi i **tre bracket** (disegno fattoriale):

```bash
for S in 0 1 2; do
  python -m substrate_core.rlvr.train_qlora_colab --bracket A_control     --seed $S
  python -m substrate_core.rlvr.train_qlora_colab --bracket B_plain_dpo    --seed $S   # ablazione (no witness)
  python -m substrate_core.rlvr.train_qlora_colab --bracket B_witness_dpo  --seed $S   # la tesi (witness iniettato)
done
python -m substrate_core.rlvr.compare --root /content/drive/MyDrive/substrate_rlvr     # -> verdetto §8
```

## Il cancello §8 (la metrica che decide)

> **Test PRIMARIO (ablazione pulita):** `B_witness_dpo` batte `B_plain_dpo` sul **solve-rate-genuino**
> (`CONFIRMED@proven AND ast_nodes(R')<ast_nodes(R) AND R'≠R`) di **≥5pp su ≥3 seed**, con **zero falsi-proven** e
> `abstain_recall`/AURC non-peggiori? Le due varianti sono identiche in tutto **tranne** il witness iniettato nel
> rejected → isola l'unico ingrediente con bit-extra reali (~2 bit/REFUTED). **Sì** → espandi. **No** → muore la
> *tesi* (per questo dominio), non il controllo — morte pulita, esito sano.
>
> `A_control` (SFT) vs `B_*` (DPO) **confonde** SFT-vs-DPO col witness → solo informativo, non il test.

Pre-gate a costo zero: se `pass@1` del base `< 5%`, il loop non ha nulla da amplificare → falsificato **senza** spendere GPU.
