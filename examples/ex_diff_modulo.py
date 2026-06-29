# STELE DI ROSETTA — divergenza REALE e famosa: il modulo dei NEGATIVI differisce tra Python e JavaScript.
#   Python  (floor-mod):  (-7) % 3 ==  2
#   JS      (trunc-mod):  (-7) % 3 === -1
# Un classico bug di migrazione che il kernel falsifica con l'input ESATTO che diverge.
def ref(x):
    return x % 3

def gen(rng):
    return rng.randint(-20, 20)

IMPL_JS = "function f(x){ return x % 3; }"
