# Harness VACUO (critica #2): la prop e' sempre vera -> non verifica NULLA.
# Prima della meta-verifica dava [v] CONFIRMED (ingannevole). Ora deve dare ABSTAIN(harness-non-adeguato).
def subject(x):
    return x * 2

def prop(x, y):
    return True          # vacuo: accetta qualsiasi output, anche sbagliato

def gen(rng):
    return rng.randint(-1000, 1000)
