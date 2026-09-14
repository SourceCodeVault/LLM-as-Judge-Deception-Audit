#!/usr/bin/env python3
"""
Fit sparse L1 logistic models over the rule incidence matrix.

For each target rule, predict whether that rule fired from the other rule
citations. Reruns from the same case are kept in the same CV fold.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
from pathlib import Path

import numpy as np


META_COLUMNS = {"case_id", "pass_id", "ground_truth", "verdict", "quadrant", "source_path"}


def stable_fold(case_id: str, folds: int) -> int:
    digest = hashlib.sha256(case_id.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % folds


def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40)))


def soft_threshold(x: np.ndarray, threshold: float) -> np.ndarray:
    return np.sign(x) * np.maximum(np.abs(x) - threshold, 0.0)


def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    eps = 1e-12
    p = np.clip(p, eps, 1.0 - eps)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def make_sample_weight(y: np.ndarray, class_weight: str) -> np.ndarray:
    if class_weight == "none":
        return np.ones_like(y, dtype=float)
    positives = float(np.sum(y == 1))
    negatives = float(np.sum(y == 0))
    weights = np.ones_like(y, dtype=float)
    if positives > 0:
        weights[y == 1] = len(y) / (2.0 * positives)
    if negatives > 0:
        weights[y == 0] = len(y) / (2.0 * negatives)
    return weights


def score(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    pred = (p >= 0.5).astype(int)
    tp = int(np.sum((y == 1) & (pred == 1)))
    tn = int(np.sum((y == 0) & (pred == 0)))
    fp = int(np.sum((y == 0) & (pred == 1)))
    fn = int(np.sum((y == 1) & (pred == 0)))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "logloss": log_loss(y, p),
        "accuracy": (tp + tn) / len(y) if len(y) else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def standardize_train_test(
    x_train: np.ndarray, x_test: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mean = np.mean(x_train, axis=0)
    scale = np.std(x_train, axis=0)
    scale[scale < 1e-12] = 1.0
    return (x_train - mean) / scale, (x_test - mean) / scale, mean, scale


def fit_l1_logistic(
    x: np.ndarray,
    y: np.ndarray,
    lam: float,
    max_iter: int,
    tol: float,
    sample_weight: np.ndarray | None = None,
) -> tuple[float, np.ndarray, int]:
    n, p = x.shape
    if sample_weight is None:
        sample_weight = np.ones(n, dtype=float)
    weight_sum = float(np.sum(sample_weight))
    prevalence = float(np.clip(np.sum(sample_weight * y) / weight_sum, 1e-6, 1.0 - 1e-6))
    intercept = math.log(prevalence / (1.0 - prevalence))
    coef = np.zeros(p, dtype=float)

    x_aug = np.column_stack([np.ones(n), x])
    weighted_x_aug = x_aug * np.sqrt(sample_weight / weight_sum)[:, None]
    lipschitz = 0.25 * (np.linalg.norm(weighted_x_aug, ord=2) ** 2)
    step = 1.0 / max(lipschitz, 1e-6)

    for iteration in range(1, max_iter + 1):
        old_intercept = intercept
        old_coef = coef.copy()

        prob = sigmoid(intercept + x @ coef)
        residual = sample_weight * (prob - y)
        intercept -= step * float(np.sum(residual) / weight_sum)
        coef = soft_threshold(coef - step * (x.T @ residual / weight_sum), step * lam)

        delta = max(abs(intercept - old_intercept), float(np.max(np.abs(coef - old_coef))) if p else 0.0)
        if delta < tol:
            return intercept, coef, iteration

    return intercept, coef, max_iter


def load_matrix(path: Path) -> tuple[list[dict[str, str]], list[str], np.ndarray, list[str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        columns = reader.fieldnames or []
    rules = [col for col in columns if col not in META_COLUMNS]
    x = np.array([[int(row[rule]) for rule in rules] for row in rows], dtype=float)
    case_ids = [row["case_id"] for row in rows]
    return rows, rules, x, case_ids


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def cv_path_for_target(
    x_all: np.ndarray,
    y: np.ndarray,
    case_ids: list[str],
    feature_names: list[str],
    lambdas: list[float],
    folds: int,
    max_iter: int,
    tol: float,
    class_weight: str,
) -> list[dict]:
    fold_ids = np.array([stable_fold(case_id, folds) for case_id in case_ids])
    rows = []
    for lam in lambdas:
        fold_scores = []
        nonzero_counts = []
        for fold in range(folds):
            train = fold_ids != fold
            test = fold_ids == fold
            if not np.any(test) or len(np.unique(y[train])) < 2:
                continue
            x_train, x_test, _, _ = standardize_train_test(x_all[train], x_all[test])
            sample_weight = make_sample_weight(y[train], class_weight)
            intercept, coef, iterations = fit_l1_logistic(x_train, y[train], lam, max_iter, tol, sample_weight)
            p_test = sigmoid(intercept + x_test @ coef)
            metrics = score(y[test], p_test)
            metrics["iterations"] = iterations
            fold_scores.append(metrics)
            nonzero_counts.append(int(np.sum(np.abs(coef) > 1e-8)))

        if not fold_scores:
            continue
        row = {
            "lambda": lam,
            "mean_nonzero": float(np.mean(nonzero_counts)),
            "mean_logloss": float(np.mean([m["logloss"] for m in fold_scores])),
            "se_logloss": float(np.std([m["logloss"] for m in fold_scores], ddof=1) / math.sqrt(len(fold_scores)))
            if len(fold_scores) > 1
            else 0.0,
            "mean_accuracy": float(np.mean([m["accuracy"] for m in fold_scores])),
            "mean_precision": float(np.mean([m["precision"] for m in fold_scores])),
            "mean_recall": float(np.mean([m["recall"] for m in fold_scores])),
            "mean_f1": float(np.mean([m["f1"] for m in fold_scores])),
        }
        rows.append(row)
    return rows


def choose_lambda(path_rows: list[dict], select_by: str) -> float:
    if select_by == "logloss_1se":
        best = min(path_rows, key=lambda r: r["mean_logloss"])
        cutoff = best["mean_logloss"] + best["se_logloss"]
        eligible = [r for r in path_rows if r["mean_logloss"] <= cutoff]
        return max(eligible, key=lambda r: r["lambda"])["lambda"]
    return max(path_rows, key=lambda r: (r["mean_f1"], r["lambda"]))["lambda"]


def main() -> None:
    parser = argparse.ArgumentParser()
    # In this repo the incidence matrix is the starting artifact; raw audit JSON
    # extraction is intentionally out of scope for the reproducible analysis.
    parser.add_argument("--incidence", default="data/rule_incidence_reruns.csv")
    parser.add_argument("--out-dir", default="results")
    parser.add_argument("--suffix", default="reruns")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--min-target-support", type=int, default=30)
    parser.add_argument("--min-feature-support", type=int, default=5)
    parser.add_argument("--lambda-min", type=float, default=1e-3)
    parser.add_argument("--lambda-max", type=float, default=0.5)
    parser.add_argument("--lambda-count", type=int, default=20)
    parser.add_argument("--select-by", choices=["f1", "logloss_1se"], default="f1")
    parser.add_argument("--class-weight", choices=["none", "balanced"], default="balanced")
    parser.add_argument("--max-iter", type=int, default=1500)
    parser.add_argument("--tol", type=float, default=1e-6)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    rows, rules, matrix, case_ids = load_matrix(Path(args.incidence))
    n = matrix.shape[0]
    supports = {rule: int(np.sum(matrix[:, i])) for i, rule in enumerate(rules)}
    lambdas = np.geomspace(args.lambda_min, args.lambda_max, args.lambda_count).tolist()

    summary_rows: list[dict] = []
    coef_rows: list[dict] = []
    path_rows_all: list[dict] = []

    for target_idx, target in enumerate(rules):
        y = matrix[:, target_idx]
        target_support = int(np.sum(y))
        if target_support < args.min_target_support or n - target_support < args.min_target_support:
            continue

        feature_indices = [
            i for i, rule in enumerate(rules)
            if i != target_idx and supports[rule] >= args.min_feature_support and n - supports[rule] >= args.min_feature_support
        ]
        feature_names = [rules[i] for i in feature_indices]
        x_all_raw = matrix[:, feature_indices]

        cv_rows = cv_path_for_target(
            x_all_raw,
            y,
            case_ids,
            feature_names,
            lambdas,
            args.folds,
            args.max_iter,
            args.tol,
            args.class_weight,
        )
        if not cv_rows:
            continue
        for row in cv_rows:
            path_rows_all.append({"target": target, **row})

        chosen_lambda = choose_lambda(cv_rows, args.select_by)
        x_std, _, mean, scale = standardize_train_test(x_all_raw, x_all_raw)
        sample_weight = make_sample_weight(y, args.class_weight)
        intercept, coef, iterations = fit_l1_logistic(x_std, y, chosen_lambda, args.max_iter, args.tol, sample_weight)
        p_full = sigmoid(intercept + x_std @ coef)
        full_metrics = score(y, p_full)
        selected = [(name, float(value)) for name, value in zip(feature_names, coef) if abs(value) > 1e-8]
        selected.sort(key=lambda item: abs(item[1]), reverse=True)
        chosen_cv = min(cv_rows, key=lambda r: abs(r["lambda"] - chosen_lambda))

        summary_rows.append({
            "target": target,
            "n": n,
            "target_support": target_support,
            "prevalence": target_support / n,
            "chosen_lambda": chosen_lambda,
            "cv_mean_f1": chosen_cv["mean_f1"],
            "cv_mean_logloss": chosen_cv["mean_logloss"],
            "cv_mean_accuracy": chosen_cv["mean_accuracy"],
            "full_f1": full_metrics["f1"],
            "full_accuracy": full_metrics["accuracy"],
            "full_precision": full_metrics["precision"],
            "full_recall": full_metrics["recall"],
            "full_mismatches": int(full_metrics["fp"] + full_metrics["fn"]),
            "nonzero": len(selected),
            "selected_features": " + ".join(name for name, _ in selected),
            "iterations": iterations,
            "class_weight": args.class_weight,
        })

        for rank, (name, value) in enumerate(selected, start=1):
            raw_scale = float(scale[feature_names.index(name)])
            raw_coef = value / raw_scale if raw_scale else 0.0
            coef_rows.append({
                "target": target,
                "rank": rank,
                "feature": name,
                "standardized_coef": value,
                "approx_raw_coef": raw_coef,
                "odds_ratio_per_raw_unit": math.exp(raw_coef) if abs(raw_coef) < 50 else float("inf"),
                "feature_support": supports[name],
            })

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_rows.sort(key=lambda r: (r["cv_mean_f1"], r["full_f1"], -r["nonzero"]), reverse=True)
    write_csv(out_dir / f"l1_logistic_rule_models_{args.suffix}.csv", summary_rows)
    write_csv(out_dir / f"l1_logistic_rule_coefficients_{args.suffix}.csv", coef_rows)
    write_csv(out_dir / f"l1_logistic_cv_path_{args.suffix}.csv", path_rows_all)

    print(f"Incidence: {args.incidence}")
    print(f"Rows: {n}")
    print(f"Rules: {', '.join(rules)}")
    print(f"Selection: {args.select_by}")
    print(f"Class weight: {args.class_weight}")
    print(f"Skipped targets with support < {args.min_target_support} or negatives < {args.min_target_support}.")
    print("\nTop sparse L1 logistic models:")
    for row in summary_rows[: args.top]:
        features = row["selected_features"] or "(intercept only)"
        print(
            f"  {row['target']:>3}: cv_f1={row['cv_mean_f1']:.3f} "
            f"full_f1={row['full_f1']:.3f} acc={row['full_accuracy']:.3f} "
            f"nonzero={row['nonzero']} lambda={row['chosen_lambda']:.5g} "
            f"features={features}"
        )

    print("\nWrote:")
    print(f"  {out_dir / f'l1_logistic_rule_models_{args.suffix}.csv'}")
    print(f"  {out_dir / f'l1_logistic_rule_coefficients_{args.suffix}.csv'}")
    print(f"  {out_dir / f'l1_logistic_cv_path_{args.suffix}.csv'}")


if __name__ == "__main__":
    main()
