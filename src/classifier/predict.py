import os
import sys
import json
import pickle
import numpy as np
import pandas as pd
from typing import Optional

import xgboost as xgb

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from behavioral_biometrics import FeatureVectorizer, BehaviorProfile, ALL_FEATURE_NAMES

SAVED_MODELS_DIR = os.path.join(os.path.dirname(__file__), "saved_models")


class BanglaCaptchaClassifier:
    def __init__(self, model_dir: str = None):
        self.model_dir = model_dir or SAVED_MODELS_DIR
        self.model: Optional[xgb.XGBClassifier] = None
        self.vectorizer = FeatureVectorizer()
        self.feature_names: list[str] = []
        self.threshold: float = 0.5
        self._loaded = False

    def load(self, model_name: str = "bangla_captcha_classifier") -> bool:
        model_path = os.path.join(self.model_dir, f"{model_name}.json")
        pipeline_path = os.path.join(self.model_dir, f"{model_name}_pipeline.json")

        if not os.path.isfile(model_path):
            print(f"Model not found: {model_path}")
            return False

        self.model = xgb.XGBClassifier()
        self.model.load_model(model_path)

        if os.path.isfile(pipeline_path):
            with open(pipeline_path, "r", encoding="utf-8") as f:
                pipeline_info = json.load(f)
            self.feature_names = pipeline_info.get("feature_names", ALL_FEATURE_NAMES[:self.model.n_features_in_])
        else:
            self.feature_names = ALL_FEATURE_NAMES[:self.model.n_features_in_]

        self._loaded = True
        print(f"Model loaded: {model_path} ({len(self.feature_names)} features)")
        return True

    def predict(
        self,
        mouse_events: list[dict] = None,
        keyboard_events: list[dict] = None,
        touch_events: list[dict] = None,
        scroll_events: list[dict] = None,
    ) -> dict:
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        profile = self.vectorizer.extract(
            mouse_events=mouse_events or [],
            keyboard_events=keyboard_events or [],
            touch_events=touch_events or [],
            scroll_events=scroll_events or [],
        )

        feature_vector = np.array(profile.feature_vector).reshape(1, -1)

        if feature_vector.shape[1] < self.model.n_features_in_:
            pad = np.zeros((1, self.model.n_features_in_ - feature_vector.shape[1]))
            feature_vector = np.concatenate([feature_vector, pad], axis=1)
        elif feature_vector.shape[1] > self.model.n_features_in_:
            feature_vector = feature_vector[:, :self.model.n_features_in_]

        proba = self.model.predict_proba(feature_vector)[0]
        prob_bot = float(proba[1])
        prediction = 1 if prob_bot >= self.threshold else 0

        return {
            "prediction": "bot" if prediction == 1 else "human",
            "is_bot": prediction == 1,
            "confidence": float(max(proba)),
            "bot_probability": prob_bot,
            "human_probability": float(proba[0]),
            "threshold": self.threshold,
            "profile": profile.to_dict(),
        }

    def predict_from_vectors(
        self,
        feature_vector: list[float],
    ) -> dict:
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        vec = np.array(feature_vector).reshape(1, -1)

        if vec.shape[1] < self.model.n_features_in_:
            pad = np.zeros((1, self.model.n_features_in_ - vec.shape[1]))
            vec = np.concatenate([vec, pad], axis=1)
        elif vec.shape[1] > self.model.n_features_in_:
            vec = vec[:, :self.model.n_features_in_]

        proba = self.model.predict_proba(vec)[0]
        prob_bot = float(proba[1])
        prediction = 1 if prob_bot >= self.threshold else 0

        return {
            "prediction": "bot" if prediction == 1 else "human",
            "is_bot": prediction == 1,
            "confidence": float(max(proba)),
            "bot_probability": prob_bot,
            "human_probability": float(proba[0]),
            "threshold": self.threshold,
        }

    def predict_batch(
        self,
        sessions: list[dict],
    ) -> list[dict]:
        results = []
        for session in sessions:
            result = self.predict(
                mouse_events=session.get("mouse_events", []),
                keyboard_events=session.get("keyboard_events", []),
                touch_events=session.get("touch_events", []),
                scroll_events=session.get("scroll_events", []),
            )
            results.append(result)
        return results

    def set_threshold(self, threshold: float):
        self.threshold = max(0.0, min(1.0, threshold))

    def get_feature_importance(self) -> dict:
        if not self._loaded or self.model is None:
            return {}

        importances = self.model.feature_importances_
        return dict(zip(self.feature_names[:len(importances)], importances.tolist()))

    def get_top_features(self, n: int = 10) -> list[dict]:
        importance = self.get_feature_importance()
        sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)
        return [{"name": name, "importance": round(float(imp), 6)} for name, imp in sorted_features[:n]]


_classifier_instance: Optional[BanglaCaptchaClassifier] = None


def get_classifier() -> BanglaCaptchaClassifier:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = BanglaCaptchaClassifier()
        _classifier_instance.load()
    return _classifier_instance


def predict_bot(mouse_events=None, keyboard_events=None, touch_events=None, scroll_events=None) -> dict:
    classifier = get_classifier()
    return classifier.predict(
        mouse_events=mouse_events,
        keyboard_events=keyboard_events,
        touch_events=touch_events,
        scroll_events=scroll_events,
    )


def predict_from_file(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sessions = data if isinstance(data, list) else [data]
    classifier = get_classifier()

    if len(sessions) == 1:
        return classifier.predict(
            mouse_events=sessions[0].get("mouse_events", []),
            keyboard_events=sessions[0].get("keyboard_events", []),
            touch_events=sessions[0].get("touch_events", []),
            scroll_events=sessions[0].get("scroll_events", []),
        )

    return {"results": classifier.predict_batch(sessions)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Predict bot/human from behavioral data")
    parser.add_argument("--file", type=str, help="JSON file with behavioral events")
    parser.add_argument("--threshold", type=float, default=0.5, help="Classification threshold")
    parser.add_argument("--model-dir", type=str, default=None, help="Model directory")
    args = parser.parse_args()

    classifier = BanglaCaptchaClassifier(model_dir=args.model_dir)
    if not classifier.load():
        print("Failed to load model. Train first with: python xgboost_train.py")
        sys.exit(1)

    classifier.set_threshold(args.threshold)

    if args.file:
        result = predict_from_file(args.file)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Provide --file with behavioral data JSON to predict.")
        print("Example: python predict.py --file session_data.json --threshold 0.5")
