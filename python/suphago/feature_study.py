"""Which hand-made board features predict how a game goes (docs/experiments.md 3-6).

    python -m suphago.feature_study --data ../data/mc1 ../data/mc2 --branch ../data/branch

1. Over all recorded boards: correlation of each feature with moves left, dying within
   30 moves and points in the next 30 moves, raw and after removing move number,
   fill and top margin (partial).
2. Same board, two moves: the move Monte Carlo played vs the random move of a branch
   game (collect_branch.py). Correlation of the feature difference with the outcome
   difference. Needs --data in the same order and --seed as the branch collection.
"""
import argparse
import math
import random

import numpy as np
from scipy.stats import spearmanr

from .collect import load_games
R = [r * 0.75 for r in [24.5, 31.5, 44, 48, 61, 78, 91, 111.5, 125.5, 154.5, 180]]
L, RW, H = 55.0, 599.0, 708.0
AREA = (RW - L) * H
NB = 16  # columns for the surface profile

def feats(s):
    fr = s['fruits']
    T = [f[0] for f in fr]; X = [f[1] for f in fr]; Y = [f[2] for f in fr]
    n = len(fr)
    out = {}
    out['fill'] = sum(math.pi * R[t] ** 2 for t in T) / AREA
    out['top_margin'] = min([y - R[t] for t, y in zip(T, Y)], default=H)   # px from the top of the box to the highest fruit
    out['n_fruits'] = n
    # surface: highest fruit edge in each column
    cols = [H] * NB
    for t, x, y in zip(T, X, Y):
        for c in range(NB):
            cx = L + (c + 0.5) * (RW - L) / NB
            dx = abs(cx - x)
            if dx < R[t]:
                cols[c] = min(cols[c], y - math.sqrt(R[t] ** 2 - dx ** 2))
    out['roughness'] = sum(abs(a - b) for a, b in zip(cols, cols[1:])) / NB
    out['height_spread'] = max(cols) - min(cols)
    # small fruits buried under bigger ones (a bigger fruit above, overlapping in x)
    buried = 0; inversions = 0
    for i in range(n):
        for j in range(n):
            if i == j: continue
            if Y[j] < Y[i] and abs(X[j] - X[i]) < R[T[i]] + R[T[j]] * 0.5:
                if T[j] > T[i] + 1: inversions += 1           # bigger (by 2+ steps) on top of smaller
                if T[i] <= 3 and T[j] >= 5: buried += 1
    out['inversions'] = inversions
    out['buried_small'] = buried
    # same-type neighbours that are almost touching (merge chances), by size
    near = 0; near_big = 0
    for i in range(n):
        for j in range(i + 1, n):
            if T[i] == T[j]:
                gap = math.hypot(X[i] - X[j], Y[i] - Y[j]) - 2 * R[T[i]]
                if gap < 15:
                    near += 1
                    if T[i] >= 6: near_big += 1
    out['near_pairs'] = near
    out['near_big_pairs'] = near_big
    # adjacent consecutive types (t next to t+1): chain structure
    chain = 0
    for i in range(n):
        for j in range(n):
            if T[j] == T[i] + 1 and T[i] >= 4:
                if math.hypot(X[i] - X[j], Y[i] - Y[j]) - R[T[i]] - R[T[j]] < 15: chain += 1
    out['chain_links'] = chain
    # monotone size gradient along x (big fruits to one side)
    mid = [(t, x) for t, x in zip(T, X) if t >= 4]
    if len(mid) >= 3 and len({t for t, _ in mid}) > 1:
        out['side_order'] = abs(float(np.corrcoef([t for t, _ in mid], [x for _, x in mid])[0, 1]))
    else:
        out['side_order'] = 0.0
    # biggest fruit: distance from the nearest bottom corner
    if n:
        k = max(range(n), key=lambda i: (T[i], Y[i]))
        out['big_corner_dist'] = min(math.hypot(X[k] - L, H - Y[k]), math.hypot(RW - X[k], H - Y[k]))
        out['max_type'] = T[k]
    else:
        out['big_corner_dist'] = 0.0; out['max_type'] = -1
    out['distinct_types'] = len(set(T))
    out['dup_types_mid'] = sum(1 for t in range(4, 10) if T.count(t) >= 2)   # unmerged twins
    return out


def study_global(data):
    seen=set(); games=[]
    for p in data:
        games += list(load_games(p, seen))
    rows=[]
    for g in games:
        S=g['steps']; n=len(S)
        for i in range(10, n, 3):
            f=feats(S[i]['s'])
            j=i+30
            f['_g30']=(S[j]['score'] if j<n else g['score'])-S[i]['score']
            f['_left']=n-i
            f['_die30']=1 if n-i<=30 else 0
            f['_turn']=i
            rows.append(f)
    print(len(rows),'states')
    keys=[k for k in rows[0] if not k.startswith('_')]
    A=np.array([[r[k] for k in keys] for r in rows],float)
    def col(k): return np.array([r[k] for r in rows],float)
    ctrl=np.column_stack([np.ones(len(rows)),col('_turn'),col('fill'),col('top_margin')])
    def resid(v):
        b,*_=np.linalg.lstsq(ctrl,v,rcond=None); return v-ctrl@b
    res={}
    for t in ['_left','_die30','_g30']:
        y=col(t); yr=resid(y)
        for i,k in enumerate(keys):
            x=A[:,i]
            r_raw=spearmanr(x,y).correlation
            r_part=np.corrcoef(resid(x),yr)[0,1] if k not in ('fill','top_margin') else float('nan')
            res.setdefault(k,{})[t]=(round(r_raw,3),round(r_part,3))
    print('feature | turns left (raw, partial) | dies in 30 | points next 30')
    for k in keys: print(k, res[k]['_left'], res[k]['_die30'], res[k]['_g30'])


def study_pairs(data, branch, seed):
    # rebuild the board list exactly as collect_branch.pick_boards did, keeping the source game
    rng = random.Random(seed); seen=set(); boards=[]
    for p in data:
        for g in load_games(p, seen):
            for i, st in enumerate(g['steps']):
                if i >= 10: boards.append((g, i))
    rng.shuffle(boards); boards = boards[:800]
    br = {b['seed']: b for b in load_games(branch)}
    ok = bad = 0; pairs=[]
    for k,(g,i) in enumerate(boards):
        b = br.get(seed+k)
        if b is None: continue
        if b['from'] != {'seed': g['seed'], 'turn': i}: bad += 1; continue
        ok += 1
        S=g['steps']; n=len(S)
        if i+1 >= n or not b['steps']: continue
        def g30(steps, j0, final, ended):
            if j0+30 < len(steps): return steps[j0+30]['score']-steps[j0]['score']
            return (final-steps[j0]['score']) if ended else None
        yo = g30(S, i+1, g['score'], True); yb = g30(b['steps'], 0, b['score'], b['ended'])
        if yo is None or yb is None: continue
        do = 1 if n-(i+1) <= 30 else 0
        db = 1 if (b['ended'] and b['turns'] <= 30) else 0
        pairs.append(dict(src=g['agent'], fo=feats(S[i+1]['s']), fb=feats(b['steps'][0]['s']), yo=yo, yb=yb, do=do, db=db))
    print('mapping ok', ok, 'mismatch', bad, 'pairs', len(pairs))
    keys=list(pairs[0]['fo'])
    for src in ['mc-combined-1ply-50','mc-combined-2ply-50']:
        P=[p for p in pairs if p['src']==src]
        dy=np.array([p['yb']-p['yo'] for p in P],float); dd=np.array([p['db']-p['do'] for p in P],float)
        print(f'\n{src}: {len(P)} pairs | random move changes points by {dy.mean():+.0f} (se {dy.std()/np.sqrt(len(P)):.0f}) over 30 moves | random worse in {np.mean(dy<0):.0%}, died more in {np.mean(dd>0):.0%}')
        print('feature | corr(d feature, d points30) | corr(d feature, d died30) | mean d feature (random - MC)')
        for k in keys:
            df=np.array([p['fb'][k]-p['fo'][k] for p in P],float)
            if df.std()==0: continue
            print(f"{k:16s} {spearmanr(df,dy).correlation:+.3f}   {spearmanr(df,dd).correlation:+.3f}   {df.mean():+.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", required=True)
    ap.add_argument("--branch", default=None)
    ap.add_argument("--seed", type=int, default=500000)
    a = ap.parse_args()
    study_global(a.data)
    if a.branch:
        study_pairs(a.data, a.branch, a.seed)


if __name__ == "__main__":
    main()
