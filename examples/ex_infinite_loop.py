# Prover CAOTICO (DoS): subject NON termina. Deve dare ABSTAIN(resource), NON impiccare il kernel.
def subject(x):
    while True:
        pass

def prop(x, y):
    return True

def gen(rng):
    return rng.randint(0, 10)
