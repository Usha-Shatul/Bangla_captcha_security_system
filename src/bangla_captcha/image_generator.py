import os
import io
import base64
import random
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from typing import Optional, Tuple, List
from dataclasses import dataclass


DEFAULT_FONT_DIR = os.path.join(os.path.dirname(__file__), "bangla_font")
FALLBACK_BANGLA = [
    "অ", "আ", "ই", "ঈ", "উ", "ঊ", "ঋ", "এ", "ঐ", "ও", "ঔ",
    "ক", "খ", "গ", "ঘ", "ঙ", "চ", "ছ", "জ", "ঝ", "ঞ",
    "ট", "ঠ", "ড", "ঢ", "ণ", "ত", "থ", "দ", "ধ", "ন",
    "প", "ফ", "ব", "ভ", "ম", "য", "র", "ল", "শ", "ষ", "স", "হ",
]


@dataclass
class ImageConfig:
    width: int = 320
    height: int = 80
    font_size: int = 36
    font_size_range: Tuple[int, int] = (30, 42)
    bg_color: Tuple[int, int, int] = (245, 245, 250)
    text_colors: List[Tuple[int, int, int]] = None
    char_spacing: int = 8
    word_spacing: int = 20
    padding: Tuple[int, int] = (20, 15)
    text_y_range: Tuple[int, int] = (10, 35)

    def __post_init__(self):
        if self.text_colors is None:
            self.text_colors = [
                (20, 20, 80),
                (80, 20, 20),
                (20, 80, 20),
                (60, 20, 60),
                (20, 60, 60),
                (100, 30, 30),
                (30, 30, 100),
            ]


class BanglaFontLoader:
    def __init__(self, font_dir: str = None):
        self.font_dir = font_dir or DEFAULT_FONT_DIR
        self._fonts = []

    def get_available_fonts(self) -> List[str]:
        if not os.path.isdir(self.font_dir):
            return []

        fonts = []
        for fname in os.listdir(self.font_dir):
            if fname.lower().endswith((".ttf", ".otf", ".ttc")):
                fonts.append(os.path.join(self.font_dir, fname))
        return fonts

    def _find_system_bangla_font(self, size: int) -> Optional[ImageFont.FreeTypeFont]:
        try:
            from font_setup import find_system_bangla_fonts, test_font_bangla_support
            for fp in find_system_bangla_fonts():
                try:
                    return ImageFont.truetype(fp, size)
                except Exception:
                    continue
            all_fonts = []
            windir = os.environ.get("WINDIR", "C:\\Windows")
            font_dir = os.path.join(windir, "Fonts")
            if os.path.isdir(font_dir):
                for fname in os.listdir(font_dir):
                    if fname.lower().endswith((".ttf", ".otf")):
                        all_fonts.append(os.path.join(font_dir, fname))
            for fp in all_fonts[:30]:
                try:
                    if test_font_bangla_support(fp):
                        return ImageFont.truetype(fp, size)
                except Exception:
                    continue
        except ImportError:
            pass
        return None

    def get_random_font(self, size: int = 36) -> ImageFont.FreeTypeFont:
        fonts = self.get_available_fonts()
        if fonts:
            try:
                return ImageFont.truetype(random.choice(fonts), size)
            except Exception:
                pass

        system_font = self._find_system_bangla_font(size)
        if system_font:
            return system_font

        for name in ["arial.ttf", "Arial.ttf", "times.ttf", "Times.ttf", "segoeui.ttf"]:
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                continue

        return ImageFont.load_default()

    def get_font(self, font_path: str = None, size: int = 36) -> ImageFont.FreeTypeFont:
        if font_path and os.path.isfile(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass
        return self.get_random_font(size)


class BanglaTextRenderer:
    def __init__(self, config: ImageConfig = None, font_loader: BanglaFontLoader = None):
        self.config = config or ImageConfig()
        self.font_loader = font_loader or BanglaFontLoader()

    def render_word(
        self,
        word: str,
        font_size: int = None,
        color: Tuple[int, int, int] = None,
        char_rotation: float = 0.0,
        char_scale: float = 1.0,
    ) -> Tuple[Image.Image, int]:
        if font_size is None:
            font_size = random.randint(*self.config.font_size_range)

        font = self.font_loader.get_random_font(font_size)
        if color is None:
            color = random.choice(self.config.text_colors)

        char_images = []
        total_width = 0
        max_height = 0

        for char in word:
            try:
                bbox = font.getbbox(char)
                char_w = bbox[2] - bbox[0]
                char_h = bbox[3] - bbox[1]
            except Exception:
                char_w = font_size
                char_h = font_size

            char_img = Image.new("RGBA", (char_w + 10, char_h + 10), (0, 0, 0, 0))
            char_draw = ImageDraw.Draw(char_img)
            char_draw.text((5, 5), char, fill=color + (255,), font=font)

            if char_scale != 1.0:
                new_w = int(char_img.width * char_scale)
                new_h = int(char_img.height * char_scale)
                char_img = char_img.resize((new_w, new_h), Image.BICUBIC)

            if char_rotation != 0.0:
                char_img = char_img.rotate(char_rotation, expand=True, fillcolor=(0, 0, 0, 0))

            char_images.append(char_img)
            total_width += char_img.width + self.config.char_spacing
            max_height = max(max_height, char_img.height)

        total_width -= self.config.char_spacing

        word_img = Image.new("RGBA", (total_width, max_height), (0, 0, 0, 0))
        x_offset = 0
        for char_img in char_images:
            y_offset = (max_height - char_img.height) // 2
            word_img.paste(char_img, (x_offset, y_offset), char_img)
            x_offset += char_img.width + self.config.char_spacing

        return word_img, total_width

    def render_text(
        self,
        text: str,
        font_size: int = None,
        apply_char_effects: bool = True,
    ) -> Image.Image:
        words = text.split()
        word_images = []
        total_width = 0
        max_height = 0

        for word in words:
            char_rot = random.uniform(-3, 3) if apply_char_effects else 0.0
            char_scale = random.uniform(0.9, 1.1) if apply_char_effects else 1.0

            word_img, word_w = self.render_word(
                word,
                font_size=font_size,
                char_rotation=char_rot,
                char_scale=char_scale,
            )
            word_images.append((word_img, word_w))
            total_width += word_w + self.config.word_spacing

        total_width -= self.config.word_spacing

        max_h = max(img.height for img, _ in word_images) if word_images else self.config.height
        text_img = Image.new("RGBA", (total_width, max_h), (0, 0, 0, 0))

        x_offset = 0
        for word_img, word_w in word_images:
            y_offset = (max_h - word_img.height) // 2
            text_img.paste(word_img, (x_offset, y_offset), word_img)
            x_offset += word_w + self.config.word_spacing

        return text_img


class ImageGenerator:
    def __init__(self, config: ImageConfig = None, font_dir: str = None):
        self.config = config or ImageConfig()
        self.font_loader = BanglaFontLoader(font_dir)
        self.renderer = BanglaTextRenderer(self.config, self.font_loader)

    def generate_base_image(self, text: str) -> Tuple[Image.Image, int]:
        text_img = self.renderer.render_text(text)

        bg = Image.new("RGB", (self.config.width, self.config.height), self.config.bg_color)

        x_offset = random.randint(self.config.padding[0], max(self.config.padding[0], 10))
        y_offset = random.randint(self.config.padding[1], max(self.config.padding[1], 10))

        if text_img.width + x_offset > self.config.width:
            x_offset = max(5, self.config.width - text_img.width - 5)
        if text_img.height + y_offset > self.config.height:
            y_offset = max(5, self.config.height - text_img.height - 5)

        bg.paste(text_img, (x_offset, y_offset), text_img)

        return bg, y_offset

    def generate_from_text(self, text: str) -> Image.Image:
        img, _ = self.generate_base_image(text)
        return img

    def add_gradient_background(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        arr = np.array(img).astype(np.float32)

        gradient = np.zeros((h, w, 3), dtype=np.float32)
        for c in range(3):
            start = random.randint(230, 250)
            end = random.randint(235, 255)
            gradient[:, :, c] = np.linspace(start, end, h).reshape(-1, 1)

        result = np.clip(arr * 0.7 + gradient * 0.3, 0, 255).astype(np.uint8)
        return Image.fromarray(result)

    def generate_varied(self, text: str) -> Image.Image:
        img, _ = self.generate_base_image(text)

        if random.random() < 0.3:
            img = self.add_gradient_background(img)

        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(random.uniform(0.9, 1.2))

        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(random.uniform(0.95, 1.05))

        return img

    def to_base64(self, img: Image.Image, format: str = "PNG") -> str:
        buf = io.BytesIO()
        img.save(buf, format=format)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def to_bytes(self, img: Image.Image, format: str = "PNG") -> bytes:
        buf = io.BytesIO()
        img.save(buf, format=format)
        return buf.getvalue()
