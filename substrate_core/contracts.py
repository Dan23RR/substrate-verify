"""substrate_core.contracts — CONTRACT-GATE: teoria-dei-tipi al confine (Pilastro 1).

Valida la FORMA dell'input PRIMA di spendere il budget d'esecuzione del kernel. Un prover (es. RED nell'arena)
che genera input FUORI-CONTRATTO — list[list[int]] dove il TASK dichiara list[int] — non guadagna un round:
i suoi input vengono SCARTATI e, se NON ne produce nemmeno uno valido, il claim e' ABSTAIN(contract) a costo
quasi-nullo (niente fuzz da 1500 trial). Costringe l'IA a combattere SOLO nello spazio degli input validi.

Onesto: la verifica e' DINAMICA (campiona l'output di gen() e ne controlla il tipo), non statica — l'inferenza
di tipo statica su Python arbitrario e' indecidibile. Ma basta a chiudere il vettore "spreco-budget-da-garbage".

Linguaggio di contratto, minimale e RICORSIVO:
    any | none | bool | int | float | number(=int|float) | str
    list[T] | tuple[T] | dict[K,V] | set[T]
    T|U  (unione, es. "int|none")
Nessuna dipendenza esterna (entra anche nel runner sandboxed senza appesantirlo).
"""
from __future__ import annotations


def check_contract(value, spec) -> bool:
    """True sse `value` rispetta il contratto `spec`. Spec sconosciuto/incoerente -> False (conservativo)."""
    spec = (spec or "any").strip().lower()
    if not spec or spec == "any":
        return True
    if "|" in spec and not spec.startswith(("list[", "tuple[", "dict[", "set[")):
        return any(check_contract(value, s) for s in spec.split("|"))
    if spec == "none":
        return value is None
    if spec == "bool":
        return isinstance(value, bool)
    if spec == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if spec == "float":
        return isinstance(value, float)
    if spec == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if spec == "str":
        return isinstance(value, str)
    if spec in ("list", "tuple", "dict", "set"):
        return isinstance(value, {"list": list, "tuple": tuple, "dict": dict, "set": set}[spec])
    if spec.startswith("list[") and spec.endswith("]"):
        return isinstance(value, list) and all(check_contract(v, spec[5:-1]) for v in value)
    if spec.startswith("tuple[") and spec.endswith("]"):
        return isinstance(value, tuple) and all(check_contract(v, spec[6:-1]) for v in value)
    if spec.startswith("set[") and spec.endswith("]"):
        return isinstance(value, set) and all(check_contract(v, spec[4:-1]) for v in value)
    if spec.startswith("dict[") and spec.endswith("]"):
        inner = spec[5:-1]
        ks, _, vs = inner.partition(",")
        return isinstance(value, dict) and all(
            check_contract(k, ks.strip()) and check_contract(v, vs.strip()) for k, v in value.items())
    return False
