# Esempio pyprop BUGGATO -> atteso REFUTED + witness (un input con duplicati).
# subject: un "sort" che per errore usa set() e PERDE i duplicati.
# invariante: l'output deve essere l'input ordinato (stessa multiplicita').
def subject(x):
    return sorted(set(x))          # BUG: set() droppa i duplicati

def prop(x, y):
    return y == sorted(x)

def gen(rng):
    n = rng.randint(0, 6)
    return [rng.randint(0, 4) for _ in range(n)]   # range piccolo -> duplicati frequenti
