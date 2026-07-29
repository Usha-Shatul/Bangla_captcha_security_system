import os
import sys
import json
import glob
import numpy as np
import pandas as pd
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from behavioral_biometrics import (
    FeatureVectorizer,
    ALL_FEATURE_NAMES,
    MOUSE_FEATURE_NAMES,
    KEYBOARD_FEATURE_NAMES,
    TOUCH_FEATURE_NAMES,
    SCROLL_FEATURE_NAMES,
)


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
HUMAN_DIR = os.path.join(DATA_DIR, "human")
BOTS_DIR = os.path.join(DATA_DIR, "bots")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")


def load_raw_sessions(data_dir: str) -> list[dict]:
    sessions = []
    if not os.path.isdir(data_dir):
        return sessions

    for fname in sorted(os.listdir(data_dir)):
        fpath = os.path.join(data_dir, fname)
        if fname.endswith(".json"):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        sessions.extend(data)
                    else:
                        sessions.append(data)
            except Exception:
                continue
        elif fname.endswith(".csv"):
            try:
                df = pd.read_csv(fpath)
                for _, row in df.iterrows():
                    sessions.append(row.to_dict())
            except Exception:
                continue

    return sessions


def session_to_features(session: dict, vectorizer: FeatureVectorizer) -> Optional[list[float]]:
    mouse_events = session.get("mouse_events") or session.get("mouse", {}).get("events", [])
    keyboard_events = session.get("keyboard_events") or session.get("keyboard", {}).get("events", [])
    touch_events = session.get("touch_events") or session.get("touch", {}).get("events", [])
    scroll_events = session.get("scroll_events") or session.get("scroll", {}).get("events", [])

    if not mouse_events and not keyboard_events:
        return None

    profile = vectorizer.extract(
        mouse_events=mouse_events,
        keyboard_events=keyboard_events,
        touch_events=touch_events,
        scroll_events=scroll_events,
    )

    vector = profile.feature_vector
    if all(v == 0 for v in vector):
        return None

    return vector


def sessions_to_dataframe(sessions: list[dict], labels: list[int], vectorizer: FeatureVectorizer) -> pd.DataFrame:
    vectors = []
    valid_labels = []

    for session, label in zip(sessions, labels):
        vec = session_to_features(session, vectorizer)
        if vec is not None:
            vectors.append(vec)
            valid_labels.append(label)

    if not vectors:
        return pd.DataFrame()

    df = pd.DataFrame(vectors, columns=ALL_FEATURE_NAMES)
    df["label"] = valid_labels
    return df


def load_dataset(split: str = "all") -> tuple[pd.DataFrame, pd.Series]:
    vectorizer = FeatureVectorizer()

    human_sessions = load_raw_sessions(HUMAN_DIR)
    bot_sessions = load_raw_sessions(BOTS_DIR)

    print(f"Loaded {len(human_sessions)} human sessions, {len(bot_sessions)} bot sessions")

    all_sessions = human_sessions + bot_sessions
    all_labels = [0] * len(human_sessions) + [1] * len(bot_sessions)

    df = sessions_to_dataframe(all_sessions, all_labels, vectorizer)

    if df.empty:
        print("Warning: No valid sessions found. Generating synthetic data.")
        df = _generate_synthetic_dataset(1000)

    if split == "train":
        df = df.sample(frac=0.8, random_state=42)
    elif split == "test":
        df = df.sample(frac=0.2, random_state=42)

    X = df.drop(columns=["label"])
    y = df["label"]

    return X, y


def load_from_processed(processed_dir: str = None) -> tuple[pd.DataFrame, pd.Series]:
    processed_dir = processed_dir or PROCESSED_DIR
    csv_path = os.path.join(processed_dir, "features.csv")

    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"No processed features found at {csv_path}")

    df = pd.read_csv(csv_path)
    X = df.drop(columns=["label"])
    y = df["label"]
    return X, y


def save_processed_dataset(X: pd.DataFrame, y: pd.Series, output_dir: str = None):
    output_dir = output_dir or PROCESSED_DIR
    os.makedirs(output_dir, exist_ok=True)

    df = X.copy()
    df["label"] = y.values
    csv_path = os.path.join(output_dir, "features.csv")
    df.to_csv(csv_path, index=False)
    print(f"Saved processed dataset to {csv_path} ({len(df)} rows, {len(df.columns)} cols)")


def _generate_synthetic_dataset(n_samples: int = 1000) -> pd.DataFrame:
    np.random.seed(42)
    n_human = n_samples // 2
    n_bot = n_samples - n_human
    n_features = len(ALL_FEATURE_NAMES)

    human_data = np.random.exponential(scale=2.0, size=(n_human, n_features))
    human_labels = np.zeros(n_human, dtype=int)

    bot_data = np.random.exponential(scale=0.5, size=(n_bot, n_features))
    bot_data[:, ALL_FEATURE_NAMES.index("mod_keyboard_total_keystrokes")] = np.random.poisson(50, n_bot)
    bot_data[:, ALL_FEATURE_NAMES.index("mod_mouse_total_distance")] = np.random.uniform(100, 500, n_bot)
    bot_labels = np.ones(n_bot, dtype=int)

    data = np.vstack([human_data, bot_data])
    labels = np.concatenate([human_labels, bot_labels])

    df = pd.DataFrame(data, columns=ALL_FEATURE_NAMES)
    df["label"] = labels

    return df.sample(frac=1, random_state=42).reset_index(drop=True)


def get_feature_stats(X: pd.DataFrame) -> dict:
    stats = {}
    for col in X.columns:
        stats[col] = {
            "mean": float(X[col].mean()),
            "std": float(X[col].std()),
            "min": float(X[col].min()),
            "max": float(X[col].max()),
            "median": float(X[col].median()),
        }
    return stats


def get_modality_stats(X: pd.DataFrame) -> dict:
    modalities = {
        "mouse": ["mod_mouse_" + f for f in MOUSE_FEATURE_NAMES],
        "keyboard": ["mod_keyboard_" + f for f in KEYBOARD_FEATURE_NAMES],
        "touch": ["mod_touch_" + f for f in TOUCH_FEATURE_NAMES],
        "scroll": ["mod_scroll_" + f for f in SCROLL_FEATURE_NAMES],
    }

    stats = {}
    for mod, cols in modalities.items():
        available = [c for c in cols if c in X.columns]
        if available:
            mod_data = X[available]
            stats[mod] = {
                "feature_count": len(available),
                "nonzero_ratio": float((mod_data != 0).any(axis=1).mean()),
                "mean_per_feature": {c: float(mod_data[c].mean()) for c in available},
            }
    return stats
