# STELE DI ROSETTA — equivalenza CONFERMATA: abs(x)+1 si comporta identico in Python e JavaScript (interi).
# Il kernel non trova divergenze su N input campionati -> CONFIRMED/empirical (regola-del-3): bit-identici fino
# a prova contraria empirica. La migrazione di QUESTA funzione e' sicura (entro il dominio campionato).
def ref(x):
    return abs(x) + 1

def gen(rng):
    return rng.randint(-1000, 1000)

IMPL_JS = "function f(x){ return Math.abs(x) + 1; }"
