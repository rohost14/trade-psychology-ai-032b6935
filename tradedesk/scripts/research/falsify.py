"""
Falsification instrument, NOT a proposed model.

Question: does ANY combination of the observables separate post-loss from
post-win behaviour? Fit the most permissive thing available - an unconstrained
logistic regression on all features at once, scored by cross-validated AUC. If
even a fitted model with free weights cannot separate, no hand-built rule can.

The fitted weights are discarded. Nothing here is a detector.
"""
import json, math, random, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
random.seed(11)
D = json.load(open("docs/research/data/signatures.json"))
T = [r for r in D["trades"] if r["next_sym"]]

def feats(r):
    gap = r["gap_to_next"]
    smg = r["session_med_gap"] or 1
    return [
        1.0,
        math.log1p(gap) if gap is not None else math.log1p(smg),   # re-entry speed
        1.0 if gap is None else 0.0,                                # overlapping
        (r["next_qty"] / r["qty"]) if r["qty"] else 1.0,            # size change
        (r["next_risk"] / r["risk"]) if r["risk"] else 1.0,         # risk change
        1.0 if r["next_und"] == r["und"] else 0.0,                  # same underlying
        1.0 if r["next_dir"] == r["dir"] else 0.0,                  # same direction
        float(r["burst_30min"]),                                    # burst
        # running_pnl REMOVED: it accumulates the current trade, so it leaks the label
        math.log1p(abs(r["running_pnl"] - r["pnl"])) * (1 if (r["running_pnl"] - r["pnl"]) < 0 else -1),
        float(r["idx"]) / max(r["n_trades"], 1),                    # position in session
        math.log1p(r["risk"]),                                      # absolute risk
    ]

X = [feats(r) for r in T]
y = [0 if r["won"] else 1 for r in T]
mu = [sum(c)/len(c) for c in zip(*X)]
sd = [ (sum((v-m)**2 for v in c)/len(c))**0.5 or 1 for c, m in zip(zip(*X), mu) ]
X = [[(v-m)/s for v, m, s in zip(row, mu, sd)] for row in X]
for row in X: row[0] = 1.0

def fit(Xtr, ytr, iters=4000, lr=0.08, l2=1e-3):
    w = [0.0]*len(Xtr[0])
    for _ in range(iters):
        g = [0.0]*len(w)
        for xi, yi in zip(Xtr, ytr):
            z = sum(a*b for a, b in zip(w, xi))
            p = 1/(1+math.exp(-max(-30, min(30, z))))
            e = p - yi
            for j, v in enumerate(xi):
                g[j] += e*v
        n = len(Xtr)
        for j in range(len(w)):
            w[j] -= lr*(g[j]/n + (l2*w[j] if j else 0))
    return w

def auc(scores, labels):
    pairs = sorted(zip(scores, labels))
    pos = sum(labels); neg = len(labels)-pos
    if not pos or not neg: return float("nan")
    rank = 0; i = 0
    ranks = {}
    order = [l for _, l in pairs]
    s = 0; r = 1
    for _, l in pairs:
        if l == 1: s += r
        r += 1
    return (s - pos*(pos+1)/2) / (pos*neg)

idx = list(range(len(X))); random.shuffle(idx)
K = 5; folds = [idx[i::K] for i in range(K)]
aucs = []
for k in range(K):
    te = set(folds[k])
    Xtr = [X[i] for i in idx if i not in te]; ytr = [y[i] for i in idx if i not in te]
    Xte = [X[i] for i in folds[k]];           yte = [y[i] for i in folds[k]]
    w = fit(Xtr, ytr)
    sc = [sum(a*b for a, b in zip(w, xi)) for xi in Xte]
    aucs.append(auc(sc, yte))
print(f"post-loss vs post-win, prior-state only, 5-fold CV AUC: "
      f"{sum(aucs)/len(aucs):.3f}   folds {[round(a,3) for a in aucs]}")

# null: same procedure on shuffled labels, to show what chance looks like here
ny = y[:]; random.shuffle(ny)
naucs = []
for k in range(K):
    te = set(folds[k])
    Xtr = [X[i] for i in idx if i not in te]; ytr = [ny[i] for i in idx if i not in te]
    Xte = [X[i] for i in folds[k]];           yte = [ny[i] for i in folds[k]]
    w = fit(Xtr, ytr)
    sc = [sum(a*b for a, b in zip(w, xi)) for xi in Xte]
    naucs.append(auc(sc, yte))
print(f"same procedure on SHUFFLED labels (chance):        "
      f"{sum(naucs)/len(naucs):.3f}   folds {[round(a,3) for a in naucs]}")
print(f"\nn={len(X)} transitions ({sum(y)} post-loss, {len(y)-sum(y)} post-win)")
