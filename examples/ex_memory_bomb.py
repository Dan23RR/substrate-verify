# Prover CAOTICO (DoS): subject alloca memoria spropositata. Deve dare ABSTAIN(resource), non OOM-crashare il kernel.
def subject(x):
    return [0] * (10 ** 10)   # ~centinaia di GB -> MemoryError nel figlio / OOM-kill, mai nel kernel

def prop(x, y):
    return True

def gen(rng):
    return 1
