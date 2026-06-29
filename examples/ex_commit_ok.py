# Commit SIMULATO (corretto): la versione giusta di running_max -> atteso CONFIRMED (zero falsi positivi).
def running_max(xs):
    """Massimi correnti: out[i] = max(xs[0..i]); inoltre len(out) deve essere == len(xs)."""
    out = []
    cur = None
    for i in range(len(xs)):
        v = xs[i]
        cur = v if cur is None else (cur if cur >= v else v)
        out.append(cur)
    return out
