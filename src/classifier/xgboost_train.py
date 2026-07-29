import os
import sys
import json
import pickle
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional

import xgboost as xgb
from sklearn.model_selection import (
    StratifiedKFold,
    cross_val_score,
    GridSearchCV,
    train_test_split,
)
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
    roc_curve,
)
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dataset import load_dataset, load_from_processed, save_processed_dataset, get_feature_stats
from behavioral_biometrics import ALL_FEATURE_NAMES

SAVED_MODELS_DIR = os.path.join(os.path.dirname(__file__), "saved_models")


def build_model(
    n_estimators: int = 300,
    max_depth: int = 6,
    learning_rate: float = 0.1,
    subsample: float = 0.8,
    colsample_bytree: int = 0.8,
    min_child_weight: int = 3,
    gamma: float = 0.1,
    reg_alpha: float = 0.0,
    reg_lambda: float = 1.0,
    scale_pos_weight: float = 1.0,
    random_state: int = 42,
) -> xgb.XGBClassifier:
    return xgb.XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        min_child_weight=min_child_weight,
        gamma=gamma,
        reg_alpha=reg_alpha,
        reg_lambda=reg_lambda,
        scale_pos_weight=scale_pos_weight,
        objective="binary:logistic",
        eval_metric="logloss",
        use_label_encoder=False,
        random_state=random_state,
        n_jobs=-1,
    )


def train(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: Optional[pd.DataFrame] = None,
    y_val: Optional[pd.Series] = None,
    params: dict = None,
    n_estimators: int = 300,
    early_stopping_rounds: int = 30,
) -> tuple[xgb.XGBClassifier, dict]:
    if params is None:
        params = {}

    n_pos = int(y_train.sum())
    n_neg = len(y_train) - n_pos
    scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

    model = build_model(
        n_estimators=n_estimators,
        scale_pos_weight=scale_pos_weight,
        **params,
    )

    eval_set = [(X_train, y_train)]
    if X_val is not None and y_val is not None:
        eval_set.append((X_val, y_val))

    model.fit(
        X_train,
        y_train,
        eval_set=eval_set,
        verbose=False,
    )

    train_pred = model.predict(X_train)
    train_proba = model.predict_proba(X_train)[:, 1]

    metrics = {
        "train_accuracy": float(accuracy_score(y_train, train_pred)),
        "train_precision": float(precision_score(y_train, train_pred, zero_division=0)),
        "train_recall": float(recall_score(y_train, train_pred, zero_division=0)),
        "train_f1": float(f1_score(y_train, train_pred, zero_division=0)),
        "train_auc": float(roc_auc_score(y_train, train_proba)),
    }

    if X_val is not None and y_val is not None:
        val_pred = model.predict(X_val)
        val_proba = model.predict_proba(X_val)[:, 1]
        metrics.update({
            "val_accuracy": float(accuracy_score(y_val, val_pred)),
            "val_precision": float(precision_score(y_val, val_pred, zero_division=0)),
            "val_recall": float(recall_score(y_val, val_pred, zero_division=0)),
            "val_f1": float(f1_score(y_val, val_pred, zero_division=0)),
            "val_auc": float(roc_auc_score(y_val, val_proba)),
            "confusion_matrix": confusion_matrix(y_val, val_pred).tolist(),
            "classification_report": classification_report(y_val, val_pred, output_dict=True),
        })

    metrics["best_iteration"] = model.best_iteration if hasattr(model, "best_iteration") else n_estimators
    metrics["feature_importance"] = dict(zip(ALL_FEATURE_NAMES[:len(model.feature_importances_)], model.feature_importances_.tolist()))

    return model, metrics


def cross_validate_model(
    X: pd.DataFrame,
    y: pd.Series,
    n_folds: int = 5,
    params: dict = None,
) -> dict:
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)

    fold_scores = {
        "accuracy": [], "precision": [], "recall": [], "f1": [], "auc": [],
    }

    for fold, (train_idx, val_idx) in enumerate(skf.split(X, y)):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        model, metrics = train(X_train, y_train, X_val, y_val, params=params)

        for key in fold_scores:
            metric_key = f"val_{key}"
            if metric_key in metrics:
                fold_scores[key].append(metrics[metric_key])

        print(f"  Fold {fold + 1}: acc={metrics.get('val_accuracy', 0):.4f} "
              f"f1={metrics.get('val_f1', 0):.4f} auc={metrics.get('val_auc', 0):.4f}")

    cv_results = {}
    for key, scores in fold_scores.items():
        cv_results[f"mean_{key}"] = float(np.mean(scores))
        cv_results[f"std_{key}"] = float(np.std(scores))

    return cv_results


def hyperparameter_search(
    X: pd.DataFrame,
    y: pd.Series,
    param_grid: dict = None,
    n_folds: int = 3,
) -> tuple[dict, dict]:
    if param_grid is None:
        param_grid = {
            "max_depth": [4, 6, 8],
            "learning_rate": [0.05, 0.1, 0.2],
            "n_estimators": [200, 300, 500],
            "min_child_weight": [1, 3, 5],
            "subsample": [0.7, 0.8, 0.9],
        }

    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

    base_model = xgb.XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        use_label_encoder=False,
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        n_jobs=-1,
    )

    grid_search = GridSearchCV(
        base_model,
        param_grid,
        cv=StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42),
        scoring="f1",
        n_jobs=-1,
        verbose=1,
    )

    grid_search.fit(X, y)

    best_params = grid_search.best_params_
    best_score = float(grid_search.best_score_)

    print(f"Best F1: {best_score:.4f}")
    print(f"Best params: {best_params}")

    return best_params, {"best_f1": best_score, "cv_results": grid_search.cv_results_}


def save_model(
    model: xgb.XGBClassifier,
    metrics: dict,
    feature_names: list[str],
    model_name: str = "bangla_captcha_classifier",
    output_dir: str = None,
):
    output_dir = output_dir or SAVED_MODELS_DIR
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    model_path = os.path.join(output_dir, f"{model_name}.json")
    model.save_model(model_path)

    pipeline = {
        "model_path": model_path,
        "feature_names": feature_names,
        "model_type": "XGBClassifier",
        "timestamp": timestamp,
        "metrics": {k: v for k, v in metrics.items() if k != "feature_importance"},
        "top_features": _get_top_features(metrics.get("feature_importance", {}), n=20),
    }

    pipeline_path = os.path.join(output_dir, f"{model_name}_pipeline.json")
    with open(pipeline_path, "w", encoding="utf-8") as f:
        json.dump(pipeline, f, indent=2, ensure_ascii=False)

    scaler_path = os.path.join(output_dir, f"{model_name}_scaler.pkl")
    scaler = StandardScaler()
    scaler.fit(np.zeros((1, len(feature_names))))
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)

    print(f"Model saved: {model_path}")
    print(f"Pipeline info saved: {pipeline_path}")
    print(f"Scaler saved: {scaler_path}")

    return {
        "model_path": model_path,
        "pipeline_path": pipeline_path,
        "scaler_path": scaler_path,
    }


def _get_top_features(importance: dict, n: int = 20) -> list[dict]:
    sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    return [{"name": name, "importance": round(float(imp), 6)} for name, imp in sorted_features[:n]]


def full_training_pipeline(
    use_processed: bool = False,
    do_hyperparam_search: bool = False,
    do_cross_validation: bool = True,
) -> dict:
    print("=" * 60)
    print("XGBoost Classifier Training Pipeline")
    print("=" * 60)

    print("\n[1/5] Loading dataset...")
    if use_processed:
        X, y = load_from_processed()
    else:
        X, y = load_dataset()

    print(f"Dataset: {len(X)} samples, {X.shape[1]} features")
    print(f"Labels: {int(y.sum())} bots, {len(y) - int(y.sum())} humans")

    print("\n[2/5] Train/test split...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Train: {len(X_train)} | Test: {len(X_test)}")

    best_params = {}
    if do_hyperparam_search:
        print("\n[3/5] Hyperparameter search...")
        best_params, search_results = hyperparameter_search(X_train, y_train)
        print(f"Search done. Best F1: {search_results['best_f1']:.4f}")
    else:
        print("\n[3/5] Skipping hyperparameter search")

    print("\n[4/5] Training final model...")
    model, metrics = train(X_train, y_train, X_test, y_test, params=best_params)

    print(f"\nFinal Metrics:")
    for key in ["val_accuracy", "val_precision", "val_recall", "val_f1", "val_auc"]:
        if key in metrics:
            print(f"  {key}: {metrics[key]:.4f}")

    cv_results = {}
    if do_cross_validation:
        print("\n[5/5] Cross-validation...")
        cv_results = cross_validate_model(X, y, params=best_params)
        print(f"\nCV Results:")
        for key, val in cv_results.items():
            print(f"  {key}: {val:.4f}")
    else:
        print("\n[5/5] Skipping cross-validation")

    print("\nSaving model...")
    save_paths = save_model(model, metrics, X.columns.tolist())

    results = {
        "metrics": metrics,
        "cv_results": cv_results,
        "best_params": best_params,
        "dataset_size": len(X),
        "feature_count": X.shape[1],
        "save_paths": save_paths,
    }

    results_path = os.path.join(SAVED_MODELS_DIR, "training_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str, ensure_ascii=False)

    print(f"\nTraining results saved: {results_path}")
    print("Pipeline complete!")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train XGBoost classifier")
    parser.add_argument("--processed", action="store_true", help="Use preprocessed features")
    parser.add_argument("--search", action="store_true", help="Run hyperparameter search")
    parser.add_argument("--no-cv", action="store_true", help="Skip cross-validation")
    args = parser.parse_args()

    full_training_pipeline(
        use_processed=args.processed,
        do_hyperparam_search=args.search,
        do_cross_validation=not args.no_cv,
    )
