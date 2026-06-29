# Commit SIMULATO (buggato): un off-by-one sottile.
def running_max(xs):
    """Massimi correnti: out[i] = max(xs[0..i]); inoltre len(out) deve essere == len(xs)."""
    out = []
    cur = None
    for i in range(len(xs) - 1):          # BUG off-by-one: salta SEMPRE l'ultimo elemento
        v = xs[i]
        cur = v if cur is None else (cur if cur >= v else v)
        out.append(cur)
    return out
