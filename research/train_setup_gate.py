#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

NUMERIC_FEATURES = [
    "ret_1",
    "ret_3",
    "ret_12",
    "range_bps",
    "rel_volume_20",
    "realized_vol_20",
    "close_vs_sma20_bps",
    "setup_score",
]
CATEGORICAL_FEATURES = ["symbol", "family", "setup_id"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Train an ML gate over named final-project setups.")
    parser.add_argument("--policy", default="config/model_policy.example.toml")
    parser.add_argument("--setup-occurrences", default=None)
    args = parser.parse_args()

    try:
        import joblib
        import pandas as pd
        from sklearn.compose import ColumnTransformer
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Install research deps with: pip install -e .[research]") from exc

    policy = tomllib.loads(Path(args.policy).read_text(encoding="utf-8"))
    setup_path = Path(args.setup_occurrences or policy["outputs"]["setup_occurrences"])
    model_path = Path(policy["model"]["model_path"])
    report_path = Path(policy["model"]["report_path"])
    train_fraction = float(policy["model"].get("train_fraction", 0.70))
    kind = str(policy["model"].get("kind", "logistic_regression"))

    df = pd.read_csv(setup_path, parse_dates=["datetime"])
    df = df.sort_values("datetime").dropna(subset=["label_forward_up"])
    missing = sorted(set(NUMERIC_FEATURES + CATEGORICAL_FEATURES + ["label_forward_up"]) - set(df.columns))
    if missing:
        raise SystemExit(f"Missing needed setup columns: {missing}")
    if len(df) < 40:
        raise SystemExit("Need at least 40 setup rows before training a useful setup gate.")

    split_idx = max(1, int(len(df) * train_fraction))
    train = df.iloc[:split_idx].copy()
    test = df.iloc[split_idx:].copy()
    if train.empty or test.empty:
        raise SystemExit("Need both train and test rows. Download more data or lower train_fraction.")

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]),
                NUMERIC_FEATURES,
            ),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )

    if kind == "random_forest":
        clf = RandomForestClassifier(n_estimators=200, min_samples_leaf=10, random_state=2198)
    elif kind == "logistic_regression":
        clf = LogisticRegression(max_iter=1000, class_weight="balanced")
    else:
        raise SystemExit("model.kind must be logistic_regression or random_forest")

    model = Pipeline([("pre", preprocessor), ("clf", clf)])
    x_train = train[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y_train = train["label_forward_up"].astype(int)
    x_test = test[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y_test = test["label_forward_up"].astype(int)

    model.fit(x_train, y_train)
    prob = model.predict_proba(x_test)[:, 1]
    pred = (prob >= 0.5).astype(int)

    try:
        auc = float(roc_auc_score(y_test, prob))
    except ValueError:
        auc = None
    try:
        ll = float(log_loss(y_test, prob, labels=[0, 1]))
    except ValueError:
        ll = None

    test_report = test[["datetime", "symbol", "setup_id", "family", "forward_return", "label_forward_up"]].copy()
    test_report["gate_probability"] = prob
    test_report["gate_take"] = pred
    grouped = (
        test_report.groupby(["setup_id", "symbol"])
        .agg(
            n=("label_forward_up", "size"),
            base_hit_rate=("label_forward_up", "mean"),
            avg_forward_return=("forward_return", "mean"),
            avg_gate_probability=("gate_probability", "mean"),
            take_rate=("gate_take", "mean"),
        )
        .reset_index()
        .sort_values(["avg_forward_return", "base_hit_rate"], ascending=False)
    )

    report = {
        "rows_total": int(len(df)),
        "rows_train": int(len(train)),
        "rows_test": int(len(test)),
        "symbols": sorted(df["symbol"].unique().tolist()),
        "setups": sorted(df["setup_id"].unique().tolist()),
        "model_kind": kind,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "test_accuracy": float(accuracy_score(y_test, pred)),
        "test_auc": auc,
        "test_log_loss": ll,
        "base_rate_test": float(y_test.mean()),
        "note": "Research report only. The model gates named setups and does not send orders.",
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "numeric_features": NUMERIC_FEATURES, "categorical_features": CATEGORICAL_FEATURES, "policy": policy}, model_path)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    grouped.to_csv(report_path.with_name("setup_gate_by_setup.csv"), index=False)
    print(json.dumps(report, indent=2))
    print(f"wrote {model_path}")
    print(f"wrote {report_path.with_name('setup_gate_by_setup.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
