
import argparse
import os
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score, recall_score, confusion_matrix

def balanced_accuracy(y_true, y_pred):
    # For binary labels {0,1}
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0,1]).ravel()
    tpr = tp / (tp + fn) if tp + fn > 0 else 0.0
    tnr = tn / (tn + fp) if tn + fp > 0 else 0.0
    return 0.5 * (tpr + tnr)

def bootstrap_ci(func, y_true, scores_or_labels, n_boot=2000, alpha=0.05, is_score=True):
    rng = np.random.default_rng(1234)
    vals = []
    n = len(y_true)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yt = y_true[idx]
        sl = scores_or_labels[idx]
        if is_score:
            vals.append(func(yt, sl))
        else:
            vals.append(func(yt, sl))
    vals = np.array(vals)
    lo, hi = np.quantile(vals, [alpha/2, 1-alpha/2])
    return float(lo), float(hi)

def main():
    ap = argparse.ArgumentParser(description="Compute Table XIV metrics from per-fold predictions")
    ap.add_argument("--input", required=True, help="CSV with columns: fold,y_true,y_score (prob)")
    ap.add_argument("--threshold", type=float, default=0.5, help="Decision threshold for labels from scores")
    ap.add_argument("--out", required=True, help="Output CSV for aggregated metrics")
    args = ap.parse_args()

    df = pd.read_csv(args.input)
    df = df.dropna(subset=["y_true", "y_score"])
    df["y_true"] = df["y_true"].astype(int)
    # Aggregate across folds (pooled OOF)
    y_true = df["y_true"].to_numpy()
    y_score = df["y_score"].to_numpy()
    y_pred = (y_score >= args.threshold).astype(int)

    # Metrics
    ba = balanced_accuracy(y_true, y_pred)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    try:
        roc = roc_auc_score(y_true, y_score)
    except ValueError:
        roc = np.nan
    try:
        pr = average_precision_score(y_true, y_score)  # PR-AUC
    except ValueError:
        pr = np.nan

    # Bootstrap CIs (simple; BCa/DeLong not implemented here)
    ba_lo, ba_hi = bootstrap_ci(lambda yt, yp: balanced_accuracy(yt, (yp>=args.threshold).astype(int)), y_true, y_score, is_score=True)
    rec_lo, rec_hi = bootstrap_ci(lambda yt, yp: recall_score(yt, (yp>=args.threshold).astype(int), zero_division=0), y_true, y_score, is_score=True)
    f1_lo, f1_hi = bootstrap_ci(lambda yt, yp: f1_score(yt, (yp>=args.threshold).astype(int), zero_division=0), y_true, y_score, is_score=True)
    roc_ci = (np.nan, np.nan) if np.isnan(roc) else bootstrap_ci(lambda yt, ys: roc_auc_score(yt, ys), y_true, y_score, is_score=True)
    pr_ci = (np.nan, np.nan) if np.isnan(pr) else bootstrap_ci(lambda yt, ys: average_precision_score(yt, ys), y_true, y_score, is_score=True)

    out = pd.DataFrame([{
        "BA": ba, "BA_CI_lo": ba_lo, "BA_CI_hi": ba_hi,
        "Recall": rec, "Recall_CI_lo": rec_lo, "Recall_CI_hi": rec_hi,
        "F1": f1, "F1_CI_lo": f1_lo, "F1_CI_hi": f1_hi,
        "ROC_AUC": roc, "ROC_AUC_CI_lo": roc_ci[0], "ROC_AUC_CI_hi": roc_ci[1],
        "PR_AUC": pr, "PR_AUC_CI_lo": pr_ci[0], "PR_AUC_CI_hi": pr_ci[1]
    }])
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    out.to_csv(args.out, index=False)

if __name__ == "__main__":
    main()
