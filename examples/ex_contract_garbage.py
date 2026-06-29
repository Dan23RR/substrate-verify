# Esempio per il CONTRACT-GATE: gen() produce input FUORI-CONTRATTO (list[list[int]]).
# Con contract="list[int]" -> tutti gli input sono invalidi -> CONTRACT_VIOLATION (ABSTAIN) a basso costo.
# Con contract="list[list[int]]" -> validi -> il subject viene eseguito normalmente.
def subject(x):
    return x                      # identita' (irrilevante: il punto e' la FORMA dell'input)

def prop(x, y):
    return y == x                 # non-vacua: rifiuta un output corrotto

def gen(rng):
    return [[rng.randint(0, 5) for _ in range(rng.randint(1, 3))]]   # list[list[int]] -> garbage per list[int]
