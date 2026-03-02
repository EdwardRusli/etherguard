"""
EtherGuard — Training Data Validator
======================================
Checks NPZ files from collect.py before training.

Usage:
    python validate_data.py

Checks: file integrity, NaN/Inf, subcarrier consistency, class balance.
"""

import sys
import numpy as np
from pathlib import Path

TRAINING_DIR = Path(__file__).parent.parent / 'data' / 'training'

BOLD   = '\033[1m'
RED    = '\033[91m'
GREEN  = '\033[92m'
YELLOW = '\033[93m'
RESET  = '\033[0m'

def ok(m):   return f"{GREEN}✓{RESET} {m}"
def warn(m): return f"{YELLOW}⚠{RESET} {m}"
def err(m):  return f"{RED}✗{RESET} {m}"


def validate():
    print("\n" + "=" * 65)
    print("  EtherGuard — Training Data Validator")
    print("=" * 65)
    print(f"  Directory: {TRAINING_DIR}\n")

    npz_files = sorted(TRAINING_DIR.glob('*.npz'))
    if not npz_files:
        print(err(f"No .npz files in {TRAINING_DIR}"))
        print("     Run: python collect.py --port /dev/ttyUSB0")
        sys.exit(1)

    issues    = []
    label_cnt = {}
    all_nsub  = []
    all_wlen  = []
    total_win = 0

    print(f"  {'File':<35} {'Label':<10} {'Win':>5} {'T':>5} {'Subs':>5} {'NaN':>4} {'Status'}")
    print("  " + "─" * 65)

    for f in npz_files:
        try:
            d = np.load(f, allow_pickle=True)
        except Exception as e:
            print(f"  {f.name:<35} {'?':<10} {'?':>5} {'?':>5} {'?':>5} {'?':>4} {err(str(e))}")
            issues.append(f"{f.name}: {e}")
            continue

        X     = d['X']
        label = str(d['label'])
        nw    = X.shape[0]
        tlen  = X.shape[1] if X.ndim >= 2 else 0
        nsub  = X.shape[2] if X.ndim == 3 else 0
        nan   = bool(np.any(~np.isfinite(X)))
        good  = not nan

        all_nsub.append(nsub)
        all_wlen.append(tlen)
        total_win += nw
        label_cnt[label] = label_cnt.get(label, 0) + nw

        ns = err("YES") if nan else "no"
        st = ok("OK") if good else warn("!")
        print(f"  {f.name:<35} {label:<10} {nw:>5} {tlen:>5} {nsub:>5} {ns:>4} {st}")

        if nan: issues.append(f"{f.name}: NaN/Inf")

    print("  " + "─" * 60)

    uniq = set(all_nsub)
    if len(uniq) > 1:
        issues.append(f"Inconsistent subcarrier counts: {uniq}")
    nsub_val = max(set(all_nsub), key=all_nsub.count) if all_nsub else 0

    print(f"\n  {BOLD}Summary{RESET}")
    print(f"  Total windows : {total_win}")
    print(f"  Subcarriers   : {nsub_val}  "
          f"{'(consistent)' if len(uniq)<=1 else err('INCONSISTENT')}")
    print()

    for lbl in ['fall', 'not_fall']:
        cnt = label_cnt.get(lbl, 0)
        pct = cnt / total_win * 100 if total_win > 0 else 0
        bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
        st  = ok("") if cnt >= 50 else warn(f"low ({cnt}<50)")
        print(f"  {lbl:10s}  {cnt:4d} ({pct:4.1f}%) [{bar}] {st}")

    if not label_cnt.get('fall'):
        issues.append("Missing 'fall' data")
    if not label_cnt.get('not_fall'):
        issues.append("Missing 'not_fall' data")

    print()
    if issues:
        print(f"  {BOLD}Issues:{RESET}")
        for i in issues:
            print(f"    {err(i)}")
        print("\n  Fix issues, then re-run collect.py if needed.")
    else:
        print(f"  {ok('All checks passed!')}")
        print("  Next: python train_local.py")

    print("=" * 65)
    return len(issues) == 0


if __name__ == '__main__':
    sys.exit(0 if validate() else 1)
