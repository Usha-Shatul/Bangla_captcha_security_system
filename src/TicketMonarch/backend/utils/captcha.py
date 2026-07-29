import os
import json
import base64
import random
import logging
from typing import Optional

log = logging.getLogger(__name__)

_categories_cache: Optional[dict] = None
_easy_metadata_cache: Optional[list] = None


def _load_easy_metadata(dataset_dir: str) -> list[dict]:
    global _easy_metadata_cache
    if _easy_metadata_cache is not None:
        return _easy_metadata_cache

    meta_path = os.path.join(dataset_dir, "metadata.json")
    if not os.path.isfile(meta_path):
        log.warning("Easy CAPTCHA metadata not found at %s", meta_path)
        _easy_metadata_cache = []
        return _easy_metadata_cache

    with open(meta_path, "r", encoding="utf-8") as f:
        _easy_metadata_cache = json.load(f)

    valid = []
    for entry in _easy_metadata_cache:
        img_path = os.path.join(dataset_dir, entry["filename"])
        if os.path.isfile(img_path):
            valid.append(entry)
        else:
            log.warning("Missing image: %s", img_path)

    _easy_metadata_cache = valid
    log.info("Loaded %d easy CAPTCHA samples from %s", len(valid), dataset_dir)
    return _easy_metadata_cache


def _load_medium_categories(dataset_dir: str) -> dict:
    global _categories_cache
    if _categories_cache is not None:
        return _categories_cache

    meta_path = os.path.join(dataset_dir, "categories.json")
    if not os.path.isfile(meta_path):
        log.warning("Medium CAPTCHA categories not found at %s", meta_path)
        _categories_cache = {}
        return _categories_cache

    with open(meta_path, "r", encoding="utf-8") as f:
        _categories_cache = json.load(f)
    return _categories_cache


def _image_to_base64(path: str) -> Optional[str]:
    try:
        with open(path, "rb") as f:
            data = f.read()
        ext = os.path.splitext(path)[1].lower()
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }.get(ext, "image/png")
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        log.warning("Failed to encode image %s: %s", path, e)
        return None


class EasyCaptchaLoader:
    def __init__(self, dataset_dir: str):
        self.dataset_dir = dataset_dir
        self.metadata = _load_easy_metadata(dataset_dir)
        self._b64_cache: dict[str, str] = {}
        for entry in self.metadata:
            img_path = os.path.join(dataset_dir, entry["filename"])
            b64 = _image_to_base64(img_path)
            if b64:
                self._b64_cache[entry["filename"]] = b64
        log.info("Easy CAPTCHA base64 cache: %d images", len(self._b64_cache))

    def is_available(self) -> bool:
        return len(self._b64_cache) > 0

    def sample(self) -> Optional[dict]:
        if not self._b64_cache:
            return None

        entry = random.choice(self.metadata)
        image_b64 = self._b64_cache.get(entry["filename"])
        if image_b64 is None:
            return None

        return {
            "captcha_type": "easy",
            "image": image_b64,
            "label": entry["label"],
            "filename": entry["filename"],
        }


class MediumCaptchaLoader:
    def __init__(self, dataset_dir: str, grid_size: int = 3,
                 target_min: int = 3, target_max: int = 5):
        self.dataset_dir = dataset_dir
        self.grid_size = grid_size
        self.target_min = target_min
        self.target_max = target_max
        self.categories = _load_medium_categories(dataset_dir)
        self._category_images = {}
        self._scan_images()

    def _scan_images(self):
        valid_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
        self._b64_cache: dict[str, str] = {}
        for cat_key in self.categories:
            cat_dir = os.path.join(self.dataset_dir, cat_key)
            if not os.path.isdir(cat_dir):
                continue
            images = []
            for fname in os.listdir(cat_dir):
                if os.path.splitext(fname)[1].lower() in valid_exts:
                    full_path = os.path.join(cat_dir, fname)
                    images.append(full_path)
            if images:
                self._category_images[cat_key] = images

        for cat_key, image_list in self._category_images.items():
            for img_path in image_list:
                b64 = _image_to_base64(img_path)
                if b64:
                    self._b64_cache[img_path] = b64

        available = {k: len(v) for k, v in self._category_images.items()}
        log.info("Medium CAPTCHA categories loaded: %s (base64 cache: %d images)",
                 available, len(self._b64_cache))

    def is_available(self) -> bool:
        return len(self._category_images) >= 2

    def get_category_list(self) -> list[dict]:
        result = []
        for key, meta in self.categories.items():
            if key in self._category_images:
                result.append({
                    "key": key,
                    "bn": meta["bn"],
                    "en": meta["en"],
                    "count": len(self._category_images[key]),
                })
        return result

    def sample(self) -> Optional[dict]:
        if not self.is_available():
            return None

        eligible_cats = [
            k for k, v in self._category_images.items()
            if len(v) >= self.target_min
        ]
        if not eligible_cats:
            eligible_cats = list(self._category_images.keys())

        target_cat = random.choice(eligible_cats)
        target_meta = self.categories[target_cat]

        all_images_in_cat = self._category_images[target_cat]
        n_target = min(
            random.randint(self.target_min, self.target_max),
            len(all_images_in_cat),
            self.grid_size * self.grid_size - 2,
        )
        target_images = random.sample(all_images_in_cat, n_target)

        distractor_cats = [k for k in self._category_images if k != target_cat]
        distractor_images = []
        needed = self.grid_size * self.grid_size - n_target
        for cat in random.sample(distractor_cats, min(len(distractor_cats), needed)):
            available = self._category_images[cat]
            take = min(needed - len(distractor_images), len(available))
            distractor_images.extend(random.sample(available, take))
            if len(distractor_images) >= needed:
                break

        grid_entries = []
        for img_path in target_images:
            grid_entries.append({
                "image": self._b64_cache.get(img_path),
                "category": target_cat,
                "is_target": True,
                "filename": os.path.basename(img_path),
            })
        for img_path in distractor_images:
            cat_key = os.path.basename(os.path.dirname(img_path))
            grid_entries.append({
                "image": self._b64_cache.get(img_path),
                "category": cat_key,
                "is_target": False,
                "filename": os.path.basename(img_path),
            })

        random.shuffle(grid_entries)

        for i, entry in enumerate(grid_entries):
            entry["position"] = i

        return {
            "captcha_type": "medium",
            "target_category": target_cat,
            "target_label_bn": target_meta["bn"],
            "target_label_en": target_meta["en"],
            "grid": grid_entries,
            "grid_size": self.grid_size,
            "total_target": n_target,
        }

    def verify(self, grid: list[dict], selected_positions: list[int],
               target_category: str) -> dict:
        correct_positions = {
            e["position"] for e in grid if e["category"] == target_category
        }
        selected_set = set(selected_positions)

        true_positives = selected_set & correct_positions
        false_positives = selected_set - correct_positions
        missed = correct_positions - selected_set

        all_correct = len(false_positives) == 0 and len(missed) == 0

        return {
            "correct": all_correct,
            "selected_count": len(selected_positions),
            "correct_count": len(true_positives),
            "incorrect_count": len(false_positives),
            "missed_count": len(missed),
            "accuracy": (
                len(true_positives) / len(correct_positions)
                if correct_positions else 0
            ),
        }
