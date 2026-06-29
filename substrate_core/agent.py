"""substrate_core.agent — L2: il LOOP EPISTEMICO basato sui WITNESS (l'esploratore caotico sopra il kernel).

Un PROVER NON-FIDATO (LLM, scriptato, o CAOTICO) interagisce SOLO via prover_seam.submit(claim) e impara dai
WITNESS firmati (refutation-guided), finche' conia un CONFIRMED o esaurisce i tentativi. Il prover NON conosce
kernel.py: la sua unica API e' il seam. L'infrastruttura regge QUALSIASI prover, anche allucinante:
  - il GAS-METER ferma i subject con loop infiniti / bombe di memoria   -> ABSTAIN, niente crash;
  - il SEAM strippa le bugie (assurance/status/witness) E il BUDGET (trials/wall_s/seed)  -> niente gaming;
  - il GATE RI-ESEGUE con un budget KERNEL-fisso (floor)                 -> un CONFIRMED-proven falso e' impossibile.

CURA DELL'AMNESIA EPISTEMICA: il loop inietta la TRAIETTORIA COMPLETA (ogni tentativo col suo witness), non solo
l'ultimo. Altrimenti un prover (LLM) ripara il bug corrente RE-INTRODUCENDO i precedenti e oscilla all'infinito
(degeneration-of-thought, Reflexion/MAR). Il witness firmato e' la base fattuale incontrovertibile del passo dopo.

L'LLM (Anthropic/OpenAI) e' UN'implementazione di Prover (LLMProver, opt-in con chiave da ENV — MAI dalla chat).
I prover deterministici (scriptato, caotico, two-bug, frozen, fake-LLM) rendono la prova-che-l'infra-regge
RIPRODUCIBILE in green-board SENZA chiave: l'LLM e' il punto d'innesto, non una dipendenza del test.
"""
from __future__ import annotations

import ast
import json
import os
import re
from typing import Optional

from .prover_seam import submit


def _write_module(workdir: str, name: str, code: str) -> str:
    os.makedirs(workdir, exist_ok=True)
    path = os.path.join(workdir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    return path


# --------------------------------------------------------------------------------------
# PARSER DIFENSIVO per output LLM non-fidato: estrae un claim JSON da prosa/markdown/JSON-troncato.
# Non solleva MAI: su fallimento ritorna un claim-sentinella che il kernel mappa ad ABSTAIN (totalita'
# preservata — il primo token reale di un LLM non puo' crashare il loop PRIMA del seam).
# --------------------------------------------------------------------------------------

def _first_balanced_object(text: str) -> Optional[str]:
    """Primo oggetto {...} bilanciato nel testo, ignorando le graffe dentro le stringhe."""
    start = text.find("{")
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None


def _parse_claim(text) -> dict:
    """LLM -> claim dict, DIFENSIVO: tollera ```json, prosa attorno, JSON troncato. Mai un'eccezione: su
    fallimento ritorna {'domain':'__unparseable__', ...} che il kernel ri-eseguira' come ABSTAIN."""
    if isinstance(text, dict):
        c = dict(text)
        c.setdefault("params", {})
        c.setdefault("kind", "untrusted-prover-claim")
        c.setdefault("target", "")
        if not isinstance(c.get("params"), dict):
            c["params"] = {}
        return c
    if not isinstance(text, str) or not text.strip():
        return {"domain": "__unparseable__", "target": "", "kind": "empty", "params": {"raw": str(text)[:200]}}
    candidates = []
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        candidates.append(m.group(1))
    bal = _first_balanced_object(text)
    if bal:
        candidates.append(bal)
    candidates.append(text.strip())
    for c in candidates:
        try:
            obj = json.loads(c)
        except Exception:  # noqa
            continue
        if isinstance(obj, dict) and obj.get("domain"):
            obj.setdefault("params", {})
            obj.setdefault("kind", "untrusted-prover-claim")
            obj.setdefault("target", "")
            if not isinstance(obj.get("params"), dict):
                obj["params"] = {}
            return obj
    return {"domain": "__unparseable__", "target": "", "kind": "malformed", "params": {"raw": text[:200]}}


# --------------------------------------------------------------------------------------
# Il LOOP EPISTEMICO — domain-agnostic. propose(target, TRAIETTORIA) -> submit -> witness nel trail -> ripeti.
# --------------------------------------------------------------------------------------

def _claim_digest(claim) -> dict:
    if not isinstance(claim, dict):
        return {"repr": str(claim)[:120]}
    return {"domain": claim.get("domain"), "target": str(claim.get("target", ""))[:160],
            "kind": claim.get("kind"), "param_keys": sorted((claim.get("params") or {}).keys())}


def _witness_key(witness):
    if not isinstance(witness, dict) or not witness:
        return None
    if "input" in witness:
        return ("io", str(witness.get("input")), str(witness.get("output")))
    return ("w", repr(sorted((str(k), str(v)) for k, v in witness.items()))[:240])


def epistemic_loop(prover, target, *, key: Optional[bytes] = None, stamp: str = "",
                   max_iters: int = 8, goal: str = "CONFIRMED") -> dict:
    """Il prover NON-FIDATO propone vedendo la TRAIETTORIA COMPLETA (cura dell'amnesia); il kernel RI-ESEGUE;
    il WITNESS firmato e' la base fattuale incontrovertibile del passo dopo. Anti-loop: se lo STESSO controesempio
    ricompare, il passo e' marcato `stalled` (degeneration-of-thought)."""
    trail, last, seen = [], None, set()
    for it in range(max_iters):
        claim = prover.propose(target, trail)              # vede TUTTO il trail, non solo l'ultimo witness
        last = submit(claim, key=key, stamp=stamp)          # l'UNICO canale; cio' che il prover sperava e' irrilevante
        v = last["certificate"]["verdict"]
        step = {"iter": it, "claim": _claim_digest(claim), "status": v["status"], "assurance": v["assurance"],
                "reason": (v["reason"] or "")[:200], "witness": v["witness"] or {}}
        wk = _witness_key(step["witness"])
        if wk is not None and wk in seen:
            step["stalled"] = True                          # stesso controesempio gia' visto: il loop non avanza
        if wk is not None:
            seen.add(wk)
        trail.append(step)
        if v["status"] == goal:
            return {"won": True, "iters": it + 1, "cert": last, "trail": trail}
    return {"won": False, "iters": max_iters, "trail": trail, "last": last}


# --------------------------------------------------------------------------------------
# Prover deterministici per la PROVA RIPRODUCIBILE che l'infra regge (nessuna chiave LLM).
# --------------------------------------------------------------------------------------

_SORT_BUGGY = ("def subject(x):\n    return sorted(set(x))\n"
               "def prop(x, y):\n    return y == sorted(x)\n"
               "def gen(rng):\n    n = rng.randint(0, 6)\n    return [rng.randint(0, 4) for _ in range(n)]\n")
_SORT_FIXED = ("def subject(x):\n    return sorted(x)\n"
               "def prop(x, y):\n    return y == sorted(x)\n"
               "def gen(rng):\n    n = rng.randint(0, 6)\n    return [rng.randint(0, 4) for _ in range(n)]\n")


class ScriptedProver:
    """Apprendimento GUIDATO-DA-REFUTAZIONE (demo a 2 stati): parte da un subject BUGGATO; appena vede un witness
    REFUTED nel trail muta al subject CORRETTO -> CONFIRMED. Stand-in deterministico minimale di un LLM."""
    def __init__(self, workdir: str):
        self.workdir, self.n = workdir, 0

    def propose(self, target, trail) -> dict:
        self.n += 1
        learned = any(s.get("witness") for s in (trail or []))   # ha visto un controesempio firmato
        path = _write_module(self.workdir, f"attempt_{self.n}.py", _SORT_FIXED if learned else _SORT_BUGGY)
        return {"domain": "pyprop", "target": path, "kind": "invariant", "params": {"trials": 400, "seed": 0}}


# --- TWO-BUG: il test che SMASCHERA l'amnesia (passa SOLO col trail completo) ------------------------------
def _twobug_src(keep_dups: bool, keep_neg: bool) -> str:
    inner = "x" if keep_neg else "[v for v in x if v >= 0]"      # keep_neg=False => bug B (droppa i negativi)
    wrapped = inner if keep_dups else "set(%s)" % inner          # keep_dups=False => bug A (dedup)
    return ("def subject(x):\n    return sorted(%s)\n" % wrapped +
            "def prop(x, y):\n    return y == sorted(x)\n" +
            "def gen(rng):\n"
            "    if rng.random() < 0.5:\n"
            "        n = rng.randint(2, 6)\n"
            "        return [rng.randint(0, 3) for _ in range(n)]\n"       # tipo A: duplicati, niente negativi
            "    base = rng.sample(range(1, 50), rng.randint(2, 5))\n"
            "    return base + [-rng.randint(1, 9)]\n")                    # tipo B: distinti + un negativo


def _classify_witness(w) -> set:
    """Dal controesempio deduci QUALE bug ha colpito: duplicati -> 'A', un negativo -> 'B'."""
    bugs = set()
    inp = (w or {}).get("input")
    try:
        xs = ast.literal_eval(inp) if isinstance(inp, str) else inp
    except Exception:  # noqa
        xs = None
    if isinstance(xs, (list, tuple)):
        xs = list(xs)
        if len(set(xs)) != len(xs):
            bugs.add("A")
        if any(isinstance(v, (int, float)) and v < 0 for v in xs):
            bugs.add("B")
    return bugs


class TwoBugProver:
    """SMASCHERA l'amnesia epistemica. Il subject ha DUE bug INDIPENDENTI (dedup + drop-negativi). Un prover che
    vede solo l'ULTIMO witness ripara quel bug ma RE-INTRODUCE l'altro -> oscilla all'infinito; uno che vede la
    TRAIETTORIA completa li ripara entrambi -> CONFIRMED. memory='full' vince, memory='last' no: il green-board
    PASSA solo perche' il loop ora inietta la storia completa (== il fix dell'amnesia)."""
    def __init__(self, workdir: str, memory: str = "full"):
        self.workdir, self.memory, self.n = workdir, memory, 0

    def propose(self, target, trail) -> dict:
        self.n += 1
        steps = trail if self.memory == "full" else (trail or [])[-1:]   # <-- la differenza-chiave
        seen = set()
        for s in steps:
            seen |= _classify_witness(s.get("witness"))
        keep_dups = "A" in seen      # ho VISTO il bug-dedup -> lo riparo (mantengo i duplicati)
        keep_neg = "B" in seen       # ho VISTO il bug-negativi -> lo riparo (mantengo i negativi)
        path = _write_module(self.workdir, f"twobug_{self.n}.py", _twobug_src(keep_dups, keep_neg))
        return {"domain": "pyprop", "target": path, "kind": "invariant", "params": {}}


class FrozenProver:
    """Ripropone SEMPRE lo stesso harness rotto con un controesempio DETERMINISTICO -> l'anti-loop deve marcare
    'stalled' (stesso witness due volte = degeneration-of-thought)."""
    _SRC = ("def subject(x):\n    return x[:-1]\n"           # droppa sempre l'ultimo elemento
            "def prop(x, y):\n    return y == x\n"
            "def gen(rng):\n    return [1, 2, 3]\n")          # input FISSO -> witness identico ad ogni giro

    def __init__(self, workdir: str):
        self.workdir, self.n = workdir, 0

    def propose(self, target, trail) -> dict:
        self.n += 1
        path = _write_module(self.workdir, f"frozen_{self.n}.py", self._SRC)
        return {"domain": "pyprop", "target": path, "kind": "invariant", "params": {}}


class ChaoticProver:
    """Il PEGGIO: bugie, harness vacui, witness fabbricati, domini allucinati, GAMING del budget (trials=0,
    wall_s~0), e (in modo lento) loop infiniti / bombe di memoria. Verifica che l'infra NON coni MAI una verita'
    falsa. `fast` salta gli attacchi gas-meter (lenti)."""
    def __init__(self, workdir: str, fast: bool = False):
        self.workdir, self.fast, self.n = workdir, fast, 0

    def propose(self, target, trail) -> dict:
        self.n += 1
        attacks = []
        if not self.fast:
            attacks += [
                ("inf_loop", "def subject(x):\n    while True: pass\ndef prop(x, y): return True\ndef gen(rng): return 1\n"),
                ("mem_bomb", "def subject(x):\n    return [0] * (10**9)\ndef prop(x, y): return True\ndef gen(rng): return 1\n"),
            ]
        attacks += [
            ("vacuous_lie", "def subject(x):\n    return x\ndef prop(x, y): return True\ndef gen(rng): return rng.randint(0, 9)\n"),
            ("garbage_domain", None),
            ("fake_witness", None),
        ]
        name, code = attacks[(self.n - 1) % len(attacks)]
        if name == "garbage_domain":
            return {"domain": "hallucinated_domain", "target": "qualsiasi", "kind": "x", "params": {}}
        if name == "fake_witness":
            return {"domain": "replay", "target": "x", "kind": "replay_exploit",
                    "params": {"input_witness": {"input": "(999, 1)"}, "input_from": "deadbeef"}}
        path = _write_module(self.workdir, f"chaos_{self.n}.py", code)
        # MENTE su assurance/status E gioca sul budget (trials=0 / wall_s~0) -> tutto strippato dal seam e
        # comunque floored dal gate (difesa in profondita'): il falso CONFIRMED da zero-evidenza e' impossibile.
        return {"domain": "pyprop", "target": path, "kind": "invariant",
                "params": {"trials": 0, "seed": 0, "wall_s": 0.001, "mem_mb": 256, "assurance": "proven", "status": "CONFIRMED"}}


# --------------------------------------------------------------------------------------
# ARENA competitiva: Blue scrive la proprieta', Red cerca l'input patologico. Il kernel adjudica.
# --------------------------------------------------------------------------------------

class BlueProver:
    """Scrive subject+prop. Red vince se trova un input che li refuta."""
    def __init__(self, workdir: str, buggy: bool = False):
        self.workdir, self.buggy = workdir, buggy

    def property_code(self):
        subj = "def subject(x):\n    return sorted(set(x))\n" if self.buggy else "def subject(x):\n    return sorted(x)\n"
        return subj + "def prop(x, y):\n    return y == sorted(x)\n"


class RedProver:
    """Scrive gen(rng) cercando input patologici (qui: liste con molti duplicati che rompono un sort che dedup-a)."""
    def __init__(self, workdir: str):
        self.workdir = workdir

    def breaker_code(self):
        return "def gen(rng):\n    n = rng.randint(2, 8)\n    return [rng.randint(0, 2) for _ in range(n)]\n"


def arena(blue: BlueProver, red: RedProver, workdir: str, *, key: Optional[bytes] = None, rounds: int = 1) -> list:
    """Blue propone la proprieta'; Red propone il breaker; il KERNEL adjudica. Red vince=REFUTED, Blue vince=CONFIRMED."""
    out = []
    for r in range(rounds):
        module = blue.property_code() + red.breaker_code()
        path = _write_module(workdir, f"arena_{r}.py", module)
        env = submit({"domain": "pyprop", "target": path, "kind": "invariant", "params": {"trials": 500, "seed": r}}, key=key)
        st = env["certificate"]["verdict"]["status"]
        out.append({"round": r, "status": st,
                    "winner": "RED (bug trovato)" if st == "REFUTED" else ("BLUE (provato)" if st == "CONFIRMED" else "nessuno (ABSTAIN)")})
    return out


# --------------------------------------------------------------------------------------
# FAKE-LLM (senza chiave): emette output PATOLOGICI per provare che il PARSER DIFENSIVO regge il loop.
# --------------------------------------------------------------------------------------

class FakeLLMProver:
    """Simula un LLM SENZA chiave: emette i tipici output PATOLOGICI (prosa, ```json, JSON troncato, dominio
    allucinato) e li fa passare per _parse_claim. Prova che il loop sopravvive al primo token reale di un LLM
    senza crashare PRIMA del seam (la totalita' del kernel non e' bypassabile da un crash a monte)."""
    def __init__(self, target: str):
        self.target, self.n = target, 0

    def _raw(self):
        valid = json.dumps({"domain": "pyprop", "target": self.target, "kind": "invariant", "params": {}})
        return [
            "Certo! Ecco la mia proposta:\n```json\n" + valid + "\n```\nSpero sia utile!",   # markdown + prosa
            "Analizzo il sort... " + valid[:max(8, len(valid) // 2)],                          # JSON TRONCATO
            "Mi dispiace, non posso aiutarti con questa richiesta.",                            # NESSUN json
            json.dumps({"domain": "dominio_allucinato", "target": "x", "params": {}}),          # dominio inventato
        ]

    def propose(self, target, trail) -> dict:
        raw = self._raw()[self.n % 4]
        self.n += 1
        return _parse_claim(raw)


# --------------------------------------------------------------------------------------
# L'LLM come Prover (OPT-IN, chiave da ENV — NON dalla chat). IMPLEMENTATO; non eseguito di default
# (la prova-che-l'infra-regge e' coi prover deterministici). E' il punto d'innesto dell'intelligenza
# esplorativa sul kernel inesorabile: l'unica cosa che richiede rete+chiave e' _call_sdk.
# --------------------------------------------------------------------------------------

LLM_SYSTEM_PROMPT = """\
Sei un PROVER non-fidato in un sistema verification-native. NON esiste alcun kernel di cui tu sappia: la tua
UNICA azione e' produrre un claim JSON inviato a un cancello d'esecuzione che RI-ESEGUE tutto. NON rispondere
con prosa. Restituisci SOLO un oggetto JSON nella forma:
  {"domain":"pyprop","kind":"invariant","params":{"code":"<python>"}}
dove <python> definisce subject(x), prop(x, y) e gen(rng) (rng = random.Random). Il cancello fuzza gen(),
esegue subject e verifica prop, poi ti restituisce un certificato a 3 vie. Se REFUTED riceverai un WITNESS
firmato (l'input/output esatto che ha rotto la prop): USALO come base fattuale incontrovertibile per MUTARE il
codice. Continua finche' ottieni CONFIRMED. NON puoi asserire un verdetto, un tier, o il budget
(trials/seed/wall_s): qualunque cosa scrivi, il cancello ri-esegue col SUO budget. Il tuo unico potere e'
SCEGLIERE il codice da sottoporre. REGOLA D'ORO: quando hai gia' visto piu' controesempi nella tua storia,
riparali TUTTI insieme — non reintrodurre un bug il cui witness e' gia' apparso (l'amnesia ti farebbe oscillare)."""


class LLMProver:
    """Prover che delega a un LLM (Anthropic/OpenAI). OPT-IN: richiede la chiave da os.environ, MAI dalla chat.
    propose() = render(traiettoria) -> chiamata SDK -> _parse_claim DIFENSIVO -> materializza il codice su file.
    Una risposta non-parsabile o un errore di rete NON crashano il loop: degradano ad ABSTAIN (totalita')."""
    def __init__(self, workdir: str, *, model: Optional[str] = None, provider: str = "anthropic",
                 max_tokens: int = 1200, max_witness_chars: int = 300):
        self.workdir, self.provider, self.max_tokens, self.max_witness_chars, self.n = (
            workdir, provider, max_tokens, max_witness_chars, 0)
        self.model = model or ("claude-sonnet-4-6" if provider == "anthropic" else "gpt-4o")
        self._seed_code = None
        if provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY assente nell'ENV (mai incollare la chiave in chat).")
        if provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY assente nell'ENV.")

    def propose(self, target, trail) -> dict:
        self.n += 1
        if self._seed_code is None and isinstance(target, str) and os.path.exists(target):
            try:
                with open(target, encoding="utf-8") as f:
                    self._seed_code = f.read()
            except Exception:  # noqa
                self._seed_code = ""
        user = self._render(target, trail)
        try:
            text = self._call_sdk(LLM_SYSTEM_PROMPT, user)         # UNICO punto che richiede chiave ENV + rete
        except Exception as e:  # noqa  (un errore SDK/rete non deve uccidere il loop)
            return {"domain": "__unparseable__", "target": "", "kind": "llm-error",
                    "params": {"raw": ("%s: %s" % (type(e).__name__, e))[:200]}}
        return self._materialize(_parse_claim(text))

    def _materialize(self, claim: dict) -> dict:
        """Se l'LLM ha messo il codice in params.code (o src/harness), scrivilo su file e punta target li'."""
        params = dict(claim.get("params") or {})
        code = params.pop("code", None) or params.pop("src", None) or params.pop("harness", None)
        if code:
            path = _write_module(self.workdir, "llm_%d.py" % self.n, str(code))
            return {"domain": claim.get("domain", "pyprop"), "target": path,
                    "kind": claim.get("kind", "invariant"), "params": params}
        return claim

    def _render(self, target, trail) -> str:
        cap = self.max_witness_chars
        lines = ["COMPITO: VERIFICA l'implementazione data scrivendo un harness pyprop (subject(x), prop(x, y), gen(rng)).",
                 'Restituisci SOLO JSON: {"domain":"pyprop","kind":"invariant","params":{"code":"<python>"}}',
                 "(nel campo code i newline vanno come \\n; puoi racchiudere il JSON in un blocco ```json).", ""]
        if self._seed_code:
            lines += ["IMPLEMENTAZIONE DA VERIFICARE (puo' contenere un bug):", "```python", self._seed_code[:2000], "```", ""]
        if trail:
            lines.append("STORIA DEI TUOI TENTATIVI (impara da OGNI controesempio, NON ripetere un bug gia' visto):")
            for s in trail:
                w = s.get("witness") or {}
                wtxt = ("input=%s -> output=%s" % (str(w.get("input"))[:cap], str(w.get("output"))[:cap])
                        if "input" in w else str(w)[:cap])
                lines.append("  - tentativo %s: %s | %s | controesempio: %s"
                             % (s["iter"], s["status"], (s.get("reason") or "")[:cap], wtxt))
            lines += ["", "Il controesempio firmato e' un FATTO incontrovertibile. CORREGGI subject() per superarlo",
                      "SENZA reintrodurre i bug dei controesempi precedenti, e ri-sottometti."]
        else:
            lines += ["PRIMO TURNO: imposta subject() IDENTICO all'implementazione data (NON correggerla ancora),",
                      "scrivi una prop() che ne cattura la correttezza e un gen() che esplora bene gli input.",
                      "Vogliamo prima ESEGUIRE il codice dato e vedere se un controesempio lo refuta."]
        return "\n".join(lines)

    def _call_sdk(self, system, user):  # pragma: no cover  (richiede LLM live + chiave ENV)
        return _llm_complete(system, user, provider=self.provider, model=self.model, max_tokens=self.max_tokens)


# --------------------------------------------------------------------------------------
# Chiamata LLM robusta + ARENA Blue-vs-Red con LLM REALI sotto il kernel inesorabile.
# Blue implementa (sort scritto a mano, niente builtin) + prop; Red scrive gen() per romperlo; il KERNEL
# adjudica (REFUTED=Red vince, CONFIRMED+harness-adeguato=Blue vince). Nessuno bara: seam + resource-gate +
# meta-verifica. Entrambi NON-FIDATI, entrambi imparano dai witness firmati sulla loro traiettoria.
# --------------------------------------------------------------------------------------

def _llm_complete(system: str, user: str, *, provider: str = "anthropic",
                  model: Optional[str] = None, max_tokens: int = 1500) -> str:
    """Chiamata LLM robusta. Neutralizza i token-bearer VUOTI iniettati da alcuni runtime (header 'Bearer '
    illegale), usa la api_key da ENV e l'endpoint UFFICIALE (mai un gateway), cosi' si usa la chiave dell'utente."""
    if provider == "anthropic":
        for v in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_CUSTOM_HEADERS"):
            if os.environ.get(v, None) == "":
                os.environ.pop(v, None)
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"),
                                     base_url="https://api.anthropic.com")
        msg = client.messages.create(model=model or "claude-sonnet-4-6", max_tokens=max_tokens,
                                     system=system, messages=[{"role": "user", "content": user}])
        return "".join(getattr(b, "text", "") for b in msg.content)
    import openai
    client = openai.OpenAI()
    r = client.chat.completions.create(
        model=model or "gpt-4o", messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    return r.choices[0].message.content or ""


def _extract_json(text) -> dict:
    """Estrae il primo oggetto JSON da prosa/markdown/JSON-troncato. {} su fallimento (mai eccezione)."""
    if isinstance(text, dict):
        return text
    if not isinstance(text, str):
        return {}
    cands = []
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        cands.append(m.group(1))
    bal = _first_balanced_object(text)
    if bal:
        cands.append(bal)
    cands.append(text.strip())
    for c in cands:
        try:
            o = json.loads(c)
            if isinstance(o, dict):
                return o
        except Exception:  # noqa
            continue
    return {}


ARENA_BLUE_SYSTEM = """\
Sei BLUE in un'arena di verifica adjudicata da un kernel che RI-ESEGUE tutto. Implementa la funzione del TASK e
fornisci l'oracolo di correttezza. Restituisci SOLO un oggetto JSON: {"subject":"<python>","prop":"<python>"} dove:
- subject(x): implementa il TASK. VIETATO usare sorted()/list.sort()/qualsiasi sort builtin: scrivi il TUO algoritmo.
- prop(x, y): l'oracolo; ritorna True sse y e' l'output CORRETTO per x secondo il TASK. QUI puoi usare i builtin
  (sorted, ecc.) come riferimento FIDATO. La prop NON deve essere vacua (il kernel meta-verifica: se accetta
  qualunque output -> ABSTAIN).
RED scrivera' un gen(rng) avversariale per trovare un input VALIDO che ROMPE il tuo subject. Se nella storia c'e'
gia' un controesempio firmato, CORREGGI subject per superarlo SENZA reintrodurre i bug precedenti. Solo il JSON."""

ARENA_RED_SYSTEM = """\
Sei RED in un'arena di verifica. BLUE ha implementato subject(x) (a mano) + prop(x,y) per il TASK dato. Scrivi
gen(rng) che produce un input VALIDO per il TASK capace di ROMPERE il subject di Blue (far fallire prop).
Restituisci SOLO un oggetto JSON: {"gen":"<python>"} (rng = random.Random). Resta NEL contratto del TASK (input
validi), ma caccia gli edge: pochi/molti elementi, duplicati, negativi, PAREGGI, frequenze miste, valori estremi.
Il kernel esegue prop(x, subject(x)) sui tuoi input: REFUTED = TU vinci. Solo il JSON."""


class LLMBlue:
    """Prover BLUE non-fidato: implementa+dimostra. Impara dai witness con cui Red lo ha rotto."""
    def __init__(self, task: str, *, model: Optional[str] = None):
        self.task, self.model = task, model

    def _render(self, history) -> str:
        lines = ["TASK:", self.task, "", "Restituisci SOLO JSON {subject, prop}.", ""]
        if history:
            lines.append("STORIA (impara dai controesempi firmati):")
            for h in history[-4:]:
                w = h.get("witness") or {}
                broke = ("  Red ti ha ROTTO: input=%s -> tuo output=%s (atteso=ordinato)"
                         % (str(w.get("input"))[:140], str(w.get("output"))[:140])) if "input" in w else ""
                lines.append("  round %d: %s (vincitore %s)%s" % (h["round"], h["status"], h["winner"], broke))
            lines.append("CORREGGI subject per superare l'ULTIMO controesempio senza reintrodurre i precedenti.")
        else:
            lines.append("Primo round: scrivi il tuo miglior sort a mano + una prop non-vacua.")
        return "\n".join(lines)

    def propose(self, history) -> dict:
        try:
            o = _extract_json(_llm_complete(ARENA_BLUE_SYSTEM, self._render(history), model=self.model))
        except Exception as e:  # noqa
            return {"subject": "", "prop": "", "_error": "%s: %s" % (type(e).__name__, e)}
        return {"subject": str(o.get("subject", "")), "prop": str(o.get("prop", ""))}


class LLMRed:
    """Prover RED non-fidato: cerca l'input patologico che refuta Blue. Impara da cio' che NON lo ha rotto."""
    def __init__(self, task: str, *, model: Optional[str] = None):
        self.task, self.model = task, model

    def _render(self, blue_code, history) -> str:
        lines = ["TASK:", self.task, "", "BLUE ha scritto (rompilo restando nel contratto del TASK):", "```python",
                 (blue_code.get("subject", "") + "\n" + blue_code.get("prop", ""))[:1800], "```",
                 "Scrivi gen(rng) per ROMPERLO. Restituisci SOLO JSON {gen}.", ""]
        if history:
            last = history[-1]
            lines.append("Round scorso: %s (vincitore %s). Se Blue ha retto, prova input PIU' cattivi/diversi."
                         % (last["status"], last["winner"]))
        return "\n".join(lines)

    def propose(self, blue_code, history) -> dict:
        try:
            o = _extract_json(_llm_complete(ARENA_RED_SYSTEM, self._render(blue_code, history), model=self.model))
        except Exception as e:  # noqa
            return {"gen": "", "_error": "%s: %s" % (type(e).__name__, e)}
        return {"gen": str(o.get("gen", ""))}


def llm_arena(blue: "LLMBlue", red: "LLMRed", workdir: str, *, key: Optional[bytes] = None, rounds: int = 4,
              contract: Optional[str] = None) -> dict:
    """Co-evoluzione adjudicata dal kernel. Ogni round: Blue (ri)scrive subject+prop vedendo la storia; Red, visto
    il codice di Blue, scrive gen() per romperlo; il kernel ri-esegue e decide. Niente puo' barare (passa dal seam).
    `contract` (es. 'list[int]') attiva il CONTRACT-GATE: gli input fuori-contratto di Red sono scartati a basso costo."""
    history, score = [], {"BLUE": 0, "RED": 0, "NONE": 0}
    params = {"contract": contract} if contract else {}
    for r in range(rounds):
        bc = blue.propose(history)
        rc = red.propose(bc, history)
        module = bc.get("subject", "") + "\n\n" + bc.get("prop", "") + "\n\n" + rc.get("gen", "")
        path = _write_module(workdir, "arena_llm_%d.py" % r, module)
        env = submit({"domain": "pyprop", "target": path, "kind": "invariant", "params": dict(params)}, key=key)
        v = env["certificate"]["verdict"]
        st = v["status"]
        winner = "RED" if st == "REFUTED" else ("BLUE" if st == "CONFIRMED" else "NONE")
        score[winner] += 1
        history.append({"round": r, "blue": bc, "red": rc, "status": st, "assurance": v["assurance"],
                        "reason": v["reason"], "witness": v["witness"] or {}, "winner": winner, "module": path})
    return {"score": score, "history": history, "rounds": rounds}


# --------------------------------------------------------------------------------------
# AUDITOR: dato il CODICE di una funzione committata, l'LLM scrive un harness AVVERSARIALE (subject che la CHIAMA
# + prop di correttezza derivata + gen). Il kernel ri-esegue: se la funzione viola la prop -> REFUTED col
# controesempio ESEGUITO. E' il cuore del guardiano CI/CD a falsi-positivi-ZERO (Pilastro 2, adapter GitHub).
# --------------------------------------------------------------------------------------

AUDITOR_SYSTEM = """\
Sei un AUDITOR di sicurezza in un sistema verification-native. Ti viene dato il CODICE di una funzione appena
committata. Scrivi un harness pyprop che cerca di ROMPERLA. Restituisci SOLO JSON con TRE DEFINIZIONI COMPLETE,
ognuna una vera istruzione `def` (NON una lambda, NON un'espressione):
  {"subject":"def subject(x):\\n    ...","prop":"def prop(x, y):\\n    ...","gen":"def gen(rng):\\n    ..."}
- subject(x): CHIAMA la funzione committata (gia' definita nello stesso file) su x e ritorna l'output.
  Esempio: "def subject(x):\\n    return nome_funzione(x)".
- prop(x, y): ritorna True sse y rispetta un invariante VERO derivato da nome/firma/docstring (NON inventato; se
  incerto usa una proprieta' METAMORFICA o un riferimento builtin fidato). NON deve essere vacua.
- gen(rng): ritorna UN SINGOLO input del tipo giusto (es. UNA lista di interi, non una lista di liste). rng e' un
  random.Random di Python: usa SOLO rng.randint(a,b), rng.choice(seq), rng.random(), rng.sample(seq,k).
  VIETATO numpy / rng.integers / np.*.
Solo il JSON, niente prosa. Il kernel ESEGUE; un REFUTED portera' un controesempio reale."""


def _primary_func(content: str) -> Optional[str]:
    m = re.search(r"^\s*def\s+(\w+)\s*\(", content or "", re.M)
    return m.group(1) if m else None


class LLMAuditor:
    """Scrive un harness avversariale {subject, prop, gen} per una funzione committata (live, chiave da ENV)."""
    def __init__(self, *, model: Optional[str] = None):
        self.model = model

    def audit(self, func_code: str, func_name: Optional[str] = None) -> dict:
        fn = func_name or _primary_func(func_code)
        user = ("CODICE COMMITTATO da auditare:\n```python\n%s\n```\n%sRestituisci JSON {subject, prop, gen} "
                "(subject deve CHIAMARE la funzione, non reimplementarla)." % (
                    func_code[:3000], ("La funzione principale e' '%s'.\n" % fn) if fn else ""))
        try:
            o = _extract_json(_llm_complete(AUDITOR_SYSTEM, user, model=self.model))
        except Exception as e:  # noqa
            return {"subject": "", "prop": "", "gen": "", "_error": "%s: %s" % (type(e).__name__, e)}
        return {"subject": str(o.get("subject", "")), "prop": str(o.get("prop", "")), "gen": str(o.get("gen", ""))}


class ScriptedAuditor:
    """Auditor DETERMINISTICO (niente LLM): harness fisso, per la prova riproducibile nel green-board."""
    def __init__(self, subject: str, prop: str, gen: str):
        self._h = {"subject": subject, "prop": prop, "gen": gen}

    def audit(self, func_code: str, func_name: Optional[str] = None) -> dict:
        return dict(self._h)
