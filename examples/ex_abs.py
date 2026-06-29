# Esempio pyprop CORRETTO -> atteso CONFIRMED.
# subject: valore assoluto; invariante: output >= 0 e |x|.
def subject(x):
    return x if x >= 0 else -x

def prop(x, y):
    return y >= 0 and (y == x or y == -x)

def gen(rng):
    return rng.randint(-10**6, 10**6)
