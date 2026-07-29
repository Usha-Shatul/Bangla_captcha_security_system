import os
import sys
import random
import base64
import io
from typing import Optional, Tuple, List
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont

from .image_generator import ImageGenerator, ImageConfig, BanglaFontLoader
from .distortion import DistortionPipeline, DistortionConfig
from .noise import NoisePipeline, NoiseConfig


DEFAULT_WORD_DIR = os.path.join(os.path.dirname(__file__), "word_dataset")

FALLBACK_WORDS = [
    "বাংলা", "ক্যাপচা", "টিকিট", "যাত্রী", "বুকিং",
    "রেল", "বাস", "ট্রেন", "স্টেশন", "প্লাটফর্ম",
    "টুইকেট", "ভ্রমণ", "যাতায়াত", "গন্তব্য", "রিজার্ভ",
    "ভাড়া", "সময়সূচী", "আসন", "জানালা", "দরজা",
    "পানি", "খাবার", "চা", "বিস্কুট", "সংবাদ",
    "স্বাগতম", "ধন্যবাদ", "নমস্কার", "শুভেচ্ছা", "অভিনন্দন",
]


@dataclass
class CaptchaConfig:
    word_count: int = 3
    word_count_range: Tuple[int, int] = (2, 4)
    min_word_length: int = 2
    max_word_length: int = 8
    width: int = 320
    height: int = 80
    font_size: int = 36
    distortion_level: int = 1
    noise_level: int = 1
    difficulty: int = 1


DIFFICULTY_PRESETS = {
    1: CaptchaConfig(
        word_count=3, width=320, height=80, font_size=38,
        distortion_level=1, noise_level=1, difficulty=1,
    ),
    2: CaptchaConfig(
        word_count=4, width=360, height=90, font_size=34,
        distortion_level=2, noise_level=2, difficulty=2,
    ),
    3: CaptchaConfig(
        word_count=5, width=400, height=95, font_size=30,
        distortion_level=3, noise_level=3, difficulty=3,
    ),
}


class BanglaWordLoader:
    def __init__(self, word_dir: str = None):
        self.word_dir = word_dir or DEFAULT_WORD_DIR
        self._words = None

    def load_words(self) -> List[str]:
        if self._words is not None:
            return self._words

        words = []

        if os.path.isdir(self.word_dir):
            for fname in os.listdir(self.word_dir):
                fpath = os.path.join(self.word_dir, fname)
                if os.path.isfile(fpath):
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            for line in f:
                                w = line.strip()
                                if w and len(w) >= 2:
                                    words.append(w)
                    except Exception:
                        continue

        if not words:
            words = FALLBACK_WORDS[:]

        self._words = words
        return words

    def get_random_words(self, count: int = 3, min_len: int = 2, max_len: int = 10) -> List[str]:
        words = self.load_words()
        filtered = [w for w in words if min_len <= len(w) <= max_len]
        if not filtered:
            filtered = words
        return random.sample(filtered, min(count, len(filtered)))

    def get_random_word(self, min_len: int = 2, max_len: int = 10) -> str:
        words = self.get_random_words(1, min_len, max_len)
        return words[0] if words else random.choice(FALLBACK_WORDS)


class BanglaCaptchaGenerator:
    def __init__(
        self,
        config: CaptchaConfig = None,
        word_dir: str = None,
        font_dir: str = None,
    ):
        self.config = config or DIFFICULTY_PRESETS[1]
        self.word_loader = BanglaWordLoader(word_dir)

        img_config = ImageConfig(
            width=self.config.width,
            height=self.config.height,
            font_size=self.config.font_size,
        )
        self.image_gen = ImageGenerator(img_config, font_dir)

        self.distortion = DistortionPipeline(self._make_distortion_config())
        self.noise = NoisePipeline(self._make_noise_config())

    def _make_distortion_config(self) -> DistortionConfig:
        level = self.config.distortion_level
        return DistortionConfig(
            wave_amplitude=2.0 + level * 1.5,
            wave_frequency=0.04 + level * 0.01,
            swirl_strength=0.1 + level * 0.15,
            swirl_radius=80.0 + level * 20,
            perspective_strength=0.05 + level * 0.05,
            rotate_range=(-3 - level * 2, 3 + level * 2),
            scale_range=(0.95 - level * 0.02, 1.05 + level * 0.02),
        )

    def _make_noise_config(self) -> NoiseConfig:
        level = self.config.noise_level
        return NoiseConfig(
            gaussian_sigma=1.0 + level * 0.8,
            salt_pepper_amount=0.01 + level * 0.01,
            speckle_amount=0.005 + level * 0.005,
            line_count=2 + level * 2,
            line_thickness=1 + level,
            dot_count=30 + level * 25,
            arc_count=1 + level,
            blur_sigma=0.3 + level * 0.2,
        )

    def generate(self, difficulty: int = None) -> dict:
        if difficulty is not None:
            self.config = DIFFICULTY_PRESETS.get(difficulty, DIFFICULTY_PRESETS[1])
            self.distortion = DistortionPipeline(self._make_distortion_config())
            self.noise = NoisePipeline(self._make_noise_config())

        word_count = random.randint(*self.config.word_count_range)
        words = self.word_loader.get_random_words(
            count=word_count,
            min_len=self.config.min_word_length,
            max_len=self.config.max_word_length,
        )

        captcha_text = " ".join(words)

        img = self.image_gen.generate_varied(captcha_text)

        if self.config.distortion_level >= 1:
            img = self.distortion.apply_all(img)

        if self.config.noise_level >= 1:
            img = self.noise.apply_all(img, level=self.config.noise_level)

        img = img.convert("RGB")

        return {
            "image": img,
            "text": captcha_text,
            "difficulty": self.config.difficulty,
            "word_count": len(words),
            "words": words,
        }

    def generate_image(self, difficulty: int = None) -> Image.Image:
        result = self.generate(difficulty)
        return result["image"]

    def generate_base64(self, difficulty: int = None) -> str:
        result = self.generate(difficulty)
        return self.image_gen.to_base64(result["image"])

    def generate_bytes(self, difficulty: int = None) -> bytes:
        result = self.generate(difficulty)
        return self.image_gen.to_bytes(result["image"])

    def generate_batch(self, count: int = 10, difficulty: int = None) -> List[dict]:
        results = []
        for _ in range(count):
            results.append(self.generate(difficulty))
        return results

    def set_difficulty(self, difficulty: int):
        self.config = DIFFICULTY_PRESETS.get(difficulty, DIFFICULTY_PRESETS[1])
        self.distortion = DistortionPipeline(self._make_distortion_config())
        self.noise = NoisePipeline(self._make_noise_config())

    def verify_text(self, captcha_text: str, user_input: str) -> bool:
        clean_captcha = captcha_text.replace(" ", "")
        clean_input = user_input.replace(" ", "")
        return clean_captcha == clean_input


_generator_instance: Optional[BanglaCaptchaGenerator] = None


def get_generator(
    difficulty: int = 1,
    word_dir: str = None,
    font_dir: str = None,
) -> BanglaCaptchaGenerator:
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = BanglaCaptchaGenerator(
            config=DIFFICULTY_PRESETS.get(difficulty, DIFFICULTY_PRESETS[1]),
            word_dir=word_dir,
            font_dir=font_dir,
        )
    else:
        _generator_instance.set_difficulty(difficulty)
    return _generator_instance
