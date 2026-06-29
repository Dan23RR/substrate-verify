"""substrate_core.rlvr.train_qlora_colab — script QLoRA-RFT/DPO PRONTO-PER-COLAB (lo lanci TU su GPU).

LOCALE = Windows NO-GPU: torch/transformers/peft/trl NON sono installati. Questo file e' VALIDATO solo
STATICAMENTE in locale (py_compile + AST-lint via verify_rlvr.py); gira su Colab/RunPod. Import pesanti LAZY.

Setup Colab (una cella):
    !pip -q install "trl>=0.12" "transformers>=4.45" peft datasets bitsandbytes accelerate
    !git clone <repo>  &&  %cd substrate_core      # cosi' `import substrate_core.rlvr` funziona
    from google.colab import drive; drive.mount('/content/drive')
    import os; os.environ['HF_TOKEN'] = ...   # MEGLIO: Colab Secrets (userdata) -> mai in chiaro in chat

I TRE BRACKET (disegno fattoriale, isola la variabile che conta):
    A_control      = SFT/RFT sui PROVEN (canale A) + casi ABSTAIN (canale C)        [baseline forte]
    B_plain_dpo    = DPO, rejected SENZA witness                                     [ablazione]
    B_witness_dpo  = DPO, rejected CON la distinguishing_string iniettata            [la tesi]
  Confronti:  A vs B  = SFT-vs-DPO ;  **B_witness vs B_plain = effetto PURO del witness** (la tesi vera).

Robusto alle versioni TRL/transformers (giugno 2026): i kwargs sono FILTRATI a quelli accettati dalla
versione installata; `tokenizer`->`processing_class` con fallback; `torch_dtype`->`dtype` con fallback.
Checkpoint su Drive (Colab disconnette). Credenziali (HF token) SOLO da env/userdata, mai in codice.
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
from typing import Any, Dict, List

BASE_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
MAX_SEQ = 384
MAX_PROMPT = 256
N_TRAIN = 400


# --------------------------------------------------------------------------- credenziali
def hf_token() -> str:
    """HF token SOLO da ambiente: env var HF_TOKEN, oppure Colab userdata. Mai hardcoded/in chat."""
    tok = os.environ.get("HF_TOKEN")
    if tok:
        return tok
    try:
        from google.colab import userdata  # type: ignore
        return userdata.get("HF_TOKEN")
    except Exception:
        return ""


# --------------------------------------------------------------------------- util robustezza-versioni
def _accepted(cls, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Tiene solo i kwargs che il costruttore di `cls` accetta nella versione installata (anti-churn TRL)."""
    try:
        params = inspect.signature(cls.__init__).parameters
    except (TypeError, ValueError):
        return kwargs
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return kwargs
    return {k: v for k, v in kwargs.items() if k in params}


def _make_trainer(trainer_cls, model, tok, train_dataset, cfg):
    """Costruisce un trainer TRL passando il tokenizer col nome giusto per la versione (processing_class | tokenizer)."""
    base = dict(model=model, args=cfg, train_dataset=train_dataset)
    try:
        return trainer_cls(**base, processing_class=tok)
    except TypeError:
        return trainer_cls(**base, tokenizer=tok)


# --------------------------------------------------------------------------- modello (lazy)
def load_model_and_tokenizer(four_bit: bool = True):
    import torch  # noqa
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    tok = AutoTokenizer.from_pretrained(BASE_MODEL, token=hf_token() or None)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    quant = None
    if four_bit:
        quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                   bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    common = dict(quantization_config=quant, device_map="auto", token=hf_token() or None)
    try:                                   # transformers nuovo: `dtype`
        model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, dtype=torch.bfloat16, **common)
    except TypeError:                      # transformers vecchio: `torch_dtype`
        model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, torch_dtype=torch.bfloat16, **common)
    return model, tok


def _prepare_peft(model, init_adapter: str = None):
    """4-bit -> prepare_model_for_kbit_training (gradient-checkpoint-safe) + LoRA. use_cache off in training.
    init_adapter: se dato ed esistente, CARICA quell'adapter (warm-start, es. da A_control) invece di LoRA fresco."""
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    model = prepare_model_for_kbit_training(model)
    model.config.use_cache = False
    if init_adapter and os.path.isdir(init_adapter) and os.path.exists(os.path.join(init_adapter, "adapter_config.json")):
        from peft import PeftModel
        print(f"[WARM-START] carico l'adapter SFT da {init_adapter} (DPO continua da li')")
        return PeftModel.from_pretrained(model, init_adapter, is_trainable=True)
    cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                     target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    return get_peft_model(model, cfg)


def _train_args(config_cls, out_dir: str, steps: int, seed: int, bsz: int, accum: int, lr: float, **extra):
    """Costruisce un *Config TRL (SFTConfig/DPOConfig) coi soli kwargs accettati dalla versione."""
    kwargs = dict(output_dir=out_dir, per_device_train_batch_size=bsz, gradient_accumulation_steps=accum,
                  max_steps=steps, learning_rate=lr, logging_steps=10, save_steps=steps, bf16=True,
                  report_to="none", seed=seed, gradient_checkpointing=True, optim="paged_adamw_8bit", **extra)
    return config_cls(**_accepted(config_cls, kwargs))


# --------------------------------------------------------------------------- generazione (pre-gate + eval)
def generate_samples(model, tok, prompt: str, k: int = 8, max_new_tokens: int = 64) -> List[str]:
    """Genera k campioni. CRITICO: model.eval() (spegne il dropout LoRA, che corrompe il greedy decoding) +
    disabilita gradient-checkpointing e riattiva la cache per la generazione. k=1 -> greedy deterministico."""
    import torch  # noqa
    was_training = model.training
    model.eval()
    if hasattr(model, "gradient_checkpointing_disable"):
        try:
            model.gradient_checkpointing_disable()
        except Exception:  # noqa
            pass
    prev_cache = getattr(model.config, "use_cache", None)
    model.config.use_cache = True
    msgs = [{"role": "user", "content": prompt}]
    text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    enc = tok(text, return_tensors="pt").to(model.device)
    gen_kwargs = dict(num_return_sequences=k, max_new_tokens=max_new_tokens, pad_token_id=tok.pad_token_id)
    gen_kwargs.update(dict(do_sample=True, temperature=0.8, top_p=0.95) if k > 1 else dict(do_sample=False))
    with torch.no_grad():
        out = model.generate(**enc, **gen_kwargs)
    if prev_cache is not None:
        model.config.use_cache = prev_cache
    if was_training:
        model.train()
    gen = out[:, enc["input_ids"].shape[1]:]
    return [tok.decode(g, skip_special_tokens=True) for g in gen]


# --------------------------------------------------------------------------- STEP 0: pre-gate
def run_pregate(model, tok, n: int = 60, seed: int = 777, k: int = 8, difficulty: int = 1,
                data: str = "synthetic", real_path: str = "") -> Dict[str, Any]:
    from substrate_core.rlvr.pregate import build_pregate_holdout, score_pregate, DEATH_THRESHOLD_PASSK
    if data == "real":
        from substrate_core.rlvr.real_factory import load_real_eval_items
        items = load_real_eval_items(real_path)[:n]
    else:
        items = build_pregate_holdout(n, seed, difficulty=difficulty)
    outputs = {it["id"]: generate_samples(model, tok, it["prompt"], k=k) for it in items}
    res = score_pregate(items, outputs, k=k)
    print(f"[PRE-GATE] pass@1={res['pass@1']:.3f} pass@{k}={res['pass@k']:.3f} "
          f"(kill se pass@{k} < {DEATH_THRESHOLD_PASSK}); headroom={res.get('headroom')}; "
          f"falsificato={res['project_falsified_zero_gpu']}")
    return res


# --------------------------------------------------------------------------- STEP 2: training
def _sft_text(tok, prompt: str, completion: str) -> str:
    msgs = [{"role": "user", "content": prompt}, {"role": "assistant", "content": completion}]
    return tok.apply_chat_template(msgs, tokenize=False)


def _sft_rows(tok, seed: int, include_abstain: bool = False, difficulty: int = 1) -> List[Dict[str, str]]:
    """Righe SFT: canale A (semplificazioni proven, tier=empirical). include_abstain=False di DEFAULT: il
    CONTROLLO e' la baseline RLVR-binaria PURA (config nota-buona = solve 0.96). NON mischiare il canale C qui:
    6 esempi abstain su 400 + overfit 12-epoche fanno COLLASSARE il modellino nel bacino 'abstain' (verificato
    in run reale: solve 0.0, abstain su tutto). L'abstain/calibrazione e' compito dei bracket DPO (coppie type-iii)."""
    from substrate_core.rlvr.factory import build_split
    from substrate_core.rlvr.pregate import format_prompt
    recs = build_split(N_TRAIN, seed, "train", difficulty=difficulty)
    rows = []
    for r in recs:
        if r["channel"] == "A":
            ans = "`%s`\n<tier>empirical</tier>" % r["completion"]
            rows.append({"text": _sft_text(tok, format_prompt(r["prompt_regex"]), ans)})
        elif r["channel"] == "C" and include_abstain:
            ans = "`%s`\n<tier>abstain</tier>" % r["completion"]
            rows.append({"text": _sft_text(tok, format_prompt(r["prompt_regex"]), ans)})
    return rows


def train_control_sft(model, tok, seed: int, out_dir: str, steps: int, difficulty: int = 1,
                      data: str = "synthetic", real_path: str = ""):
    """BRACCIO A: SFT/RFT sui PROVEN — controllo RLVR-binario PURO. data='real' -> regex reali (headroom)."""
    from datasets import Dataset
    from trl import SFTConfig, SFTTrainer
    if data == "real":
        from substrate_core.rlvr.real_factory import load_real_sft_rows
        rows = load_real_sft_rows(tok, real_path)
    else:
        rows = _sft_rows(tok, seed, include_abstain=False, difficulty=difficulty)
    ds = Dataset.from_list(rows)
    model = _prepare_peft(model)
    cfg = _train_args(SFTConfig, out_dir, steps, seed, bsz=4, accum=4, lr=2e-4,
                      dataset_text_field="text", max_seq_length=MAX_SEQ, max_length=MAX_SEQ, packing=False)
    trainer = _make_trainer(SFTTrainer, model, tok, ds, cfg)
    trainer.train()
    model.save_pretrained(out_dir)
    return model


def train_dpo(model, tok, seed: int, out_dir: str, steps: int, inject_witness: bool, difficulty: int = 1,
              init_adapter: str = None, data: str = "synthetic", real_path: str = ""):
    """BRACCI B: DPO sulle coppie. inject_witness distingue B_witness (tesi) da B_plain (ablazione).
    init_adapter: warm-start dall'SFT (A_control). data='real' -> regex reali (headroom reale)."""
    from datasets import Dataset
    from trl import DPOConfig, DPOTrainer
    if data == "real":
        from substrate_core.rlvr.real_factory import load_real_dpo
        pairs = load_real_dpo(real_path, inject_witness=inject_witness)
    else:
        from substrate_core.rlvr.dpo_builder import build_dpo_pairs
        pairs = build_dpo_pairs(N_TRAIN, seed, inject_witness=inject_witness, difficulty=difficulty)
    ds = Dataset.from_list([{"prompt": p["prompt"], "chosen": p["chosen"], "rejected": p["rejected"]} for p in pairs])
    model = _prepare_peft(model, init_adapter=init_adapter)
    cfg = _train_args(DPOConfig, out_dir, steps, seed, bsz=2, accum=8, lr=5e-5,
                      beta=0.1, max_length=MAX_SEQ, max_prompt_length=MAX_PROMPT)
    trainer = _make_trainer(DPOTrainer, model, tok, ds, cfg)
    trainer.train()
    model.save_pretrained(out_dir)
    return model


# --------------------------------------------------------------------------- STEP 3: eval
def evaluate_checkpoint(model, tok, seed: int, n: int = 80, difficulty: int = 1,
                        data: str = "synthetic", real_path: str = "") -> Dict[str, Any]:
    from substrate_core.rlvr.factory import build_split
    from substrate_core.rlvr.pregate import format_prompt, extract_regex
    from substrate_core.rlvr.evaluator import evaluate
    from substrate_core.rlvr.reward import reward
    items, outputs = [], {}
    if data == "real":
        from substrate_core.rlvr.real_factory import load_real_eval_items
        for it in load_real_eval_items(real_path):
            items.append({"id": it["id"], "bloated": it["bloated"], "gold": it["gold"]})
            outputs[it["id"]] = generate_samples(model, tok, it["prompt"], k=1)[0]
        return _finish_eval(items, outputs, evaluate, reward, extract_regex)
    hold = build_split(n, seed + 10_000, "holdout", difficulty=difficulty)
    for r in hold:
        if r["channel"] == "A":
            iid = r["task_id"]
            items.append({"id": iid, "bloated": r["prompt_regex"], "gold": r["completion"]})
            outputs[iid] = generate_samples(model, tok, format_prompt(r["prompt_regex"]), k=1)[0]
        elif r["channel"] == "C":
            iid = "C-" + r["prompt_regex"]
            items.append({"id": iid, "bloated": r["prompt_regex"], "expected_status": "ABSTAIN"})
            outputs[iid] = generate_samples(model, tok, format_prompt(r["prompt_regex"]), k=1)[0]
    return _finish_eval(items, outputs, evaluate, reward, extract_regex)


def _finish_eval(items, outputs, evaluate, reward, extract_regex) -> Dict[str, Any]:
    """evaluate + DIAGNOSI (output grezzi salvati). Condiviso da eval sintetico e reale."""
    metrics = evaluate(items, outputs)
    samples = []
    for it in items[:12]:
        out = outputs.get(it["id"], "")
        rp = extract_regex(out)
        rw = reward(it["bloated"], rp)["reward"] if (rp and not it.get("expected_status")) else None
        samples.append({"bloated": it["bloated"], "raw_output": out[:200], "extracted": rp, "reward": rw,
                        "expected": it.get("expected_status", "simplify")})
    metrics["samples"] = samples
    return metrics


# --------------------------------------------------------------------------- main
BRACKETS = ("A_control", "B_plain_dpo", "B_witness_dpo")


def main():
    ap = argparse.ArgumentParser(description="Substrate-RLVR QLoRA su Colab/RunPod.")
    ap.add_argument("--bracket", choices=BRACKETS, default="A_control")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--difficulty", type=int, default=2, choices=[1, 2, 3],
                    help="complessita' seed: 1=facile (soffitto ~0.9), 2=consigliata (headroom), 3=dura")
    ap.add_argument("--drive", default="/content/drive/MyDrive/substrate_rlvr")
    ap.add_argument("--data", choices=["synthetic", "real"], default="synthetic",
                    help="real = regex REALI da GitHub (headroom reale, copertura 53-59%% del mondo reale)")
    ap.add_argument("--skip-pregate", action="store_true")
    ap.add_argument("--no-warmstart", action="store_true",
                    help="bracket B: NON partire dall'adapter SFT di A_control (DPO da base)")
    ap.add_argument("--eval-only", action="store_true",
                    help="NON addestrare: carica l'adapter gia' salvato in out_dir e fai SOLO l'eval (robusto ai disconnect Colab)")
    args = ap.parse_args()

    _RD = os.path.join(os.path.dirname(__file__), "data", "real")
    real_train, real_hold = os.path.join(_RD, "train_base.jsonl"), os.path.join(_RD, "holdout_base.jsonl")
    tag = f"{args.bracket}_{args.data}_d{args.difficulty}_seed{args.seed}"
    out_dir = os.path.join(args.drive, tag)
    os.makedirs(out_dir, exist_ok=True)
    model, tok = load_model_and_tokenizer(four_bit=True)

    # EVAL-ONLY: carica l'adapter gia' addestrato (es. dopo un disconnect Colab post-training) e valuta soltanto.
    if args.eval_only:
        if os.path.exists(os.path.join(out_dir, "adapter_config.json")):
            from peft import PeftModel
            print(f"[EVAL-ONLY] carico l'adapter da {out_dir}")
            model = PeftModel.from_pretrained(model, out_dir)
        else:
            print(f"[EVAL-ONLY] nessun adapter in {out_dir}: valuto il BASE (nessun training trovato)")
        metrics = evaluate_checkpoint(model, tok, args.seed, difficulty=args.difficulty,
                                      data=args.data, real_path=real_hold)
        metrics["bracket"], metrics["seed"], metrics["difficulty"], metrics["data"] = \
            args.bracket, args.seed, args.difficulty, args.data
        with open(os.path.join(out_dir, "eval_report.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        b = {k: v for k, v in metrics.items() if k not in ("risk_coverage", "samples")}
        print("[EVAL]", json.dumps(b, ensure_ascii=False))
        print("[CAMPIONI]:")
        for s in metrics.get("samples", [])[:8]:
            print(f"   {s['bloated']!r:>26} -> {s['raw_output']!r} -> {s['extracted']!r} reward={s['reward']}")
        return

    if not args.skip_pregate:
        pre = run_pregate(model, tok, seed=args.seed, difficulty=args.difficulty,
                          data=args.data, real_path=real_hold)
        with open(os.path.join(out_dir, "pregate.json"), "w", encoding="utf-8") as f:
            json.dump(pre, f, ensure_ascii=False, indent=2)
        if pre["project_falsified_zero_gpu"]:
            print("STOP: pre-gate fallito (pass@1 < soglia). Progetto falsificato a costo ~zero. Non addestro.")
            return

    # warm-start dei bracket B dall'adapter SFT di A_control (stesso data/difficolta'/seed) se presente
    sft_dir = None if args.no_warmstart else os.path.join(args.drive, f"A_control_{args.data}_d{args.difficulty}_seed{args.seed}")
    if args.bracket == "A_control":
        model = train_control_sft(model, tok, args.seed, out_dir, args.steps, difficulty=args.difficulty,
                                  data=args.data, real_path=real_train)
    elif args.bracket == "B_plain_dpo":
        model = train_dpo(model, tok, args.seed, out_dir, args.steps, inject_witness=False,
                          difficulty=args.difficulty, init_adapter=sft_dir, data=args.data, real_path=real_train)
    else:  # B_witness_dpo
        model = train_dpo(model, tok, args.seed, out_dir, args.steps, inject_witness=True,
                          difficulty=args.difficulty, init_adapter=sft_dir, data=args.data, real_path=real_train)

    metrics = evaluate_checkpoint(model, tok, args.seed, difficulty=args.difficulty,
                                  data=args.data, real_path=real_hold)
    metrics["bracket"], metrics["seed"], metrics["difficulty"], metrics["data"] = \
        args.bracket, args.seed, args.difficulty, args.data
    with open(os.path.join(out_dir, "eval_report.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    brief = {k: v for k, v in metrics.items() if k not in ("risk_coverage", "samples")}
    print("[EVAL]", json.dumps(brief, ensure_ascii=False))
    print("[CAMPIONI] (prompt-regex -> output del modello -> regex estratta -> reward):")
    for s in metrics.get("samples", [])[:8]:
        print(f"   {s['bloated']!r:>22} -> {s['raw_output']!r} -> {s['extracted']!r} reward={s['reward']}")
    if metrics["false_proven_violation"]:
        print("VIOLAZIONE: falsi-proven > 0 (peccato cardinale). Checkpoint INVALIDO a prescindere dall'accuracy.")


if __name__ == "__main__":
    main()
