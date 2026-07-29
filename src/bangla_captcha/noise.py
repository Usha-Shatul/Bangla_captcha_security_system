import os
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from typing import Optional, Tuple, List
from dataclasses import dataclass


@dataclass
class NoiseConfig:
    gaussian_sigma: float = 1.5
    salt_pepper_amount: float = 0.02
    speckle_amount: float = 0.01
    line_count: int = 4
    line_thickness: int = 2
    dot_count: int = 50
    arc_count: int = 3
    blur_sigma: float = 0.5


class GaussianNoise:
    def __init__(self, sigma: float = 1.5):
        self.sigma = sigma

    def apply(self, img: Image.Image) -> Image.Image:
        arr = np.array(img).astype(np.float32)
        noise = np.random.normal(0, self.sigma, arr.shape)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        return Image.fromarray(arr)


class SaltPepperNoise:
    def __init__(self, amount: float = 0.02):
        self.amount = amount

    def apply(self, img: Image.Image) -> Image.Image:
        arr = np.array(img)
        h, w = arr.shape[:2]
        total_pixels = h * w
        num_salt = int(total_pixels * self.amount / 2)
        num_pepper = int(total_pixels * self.amount / 2)

        for c in range(arr.shape[2] if len(arr.shape) > 2 else 1):
            salt_y = np.random.randint(0, h, num_salt)
            salt_x = np.random.randint(0, w, num_salt)
            if len(arr.shape) == 3:
                arr[salt_y, salt_x, c] = 255
            else:
                arr[salt_y, salt_x] = 255

            pepper_y = np.random.randint(0, h, num_pepper)
            pepper_x = np.random.randint(0, w, num_pepper)
            if len(arr.shape) == 3:
                arr[pepper_y, pepper_x, c] = 0
            else:
                arr[pepper_y, pepper_x] = 0

        return Image.fromarray(arr)


class SpeckleNoise:
    def __init__(self, amount: float = 0.01):
        self.amount = amount

    def apply(self, img: Image.Image) -> Image.Image:
        arr = np.array(img).astype(np.float32)
        noise = np.random.randn(*arr.shape) * self.amount * arr
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        return Image.fromarray(arr)


class LineNoise:
    def __init__(self, line_count: int = 4, thickness: int = 2):
        self.line_count = line_count
        self.thickness = thickness

    def apply(self, img: Image.Image) -> Image.Image:
        draw = ImageDraw.Draw(img)
        w, h = img.size

        for _ in range(self.line_count):
            x1 = random.randint(0, w)
            y1 = random.randint(0, h)
            x2 = random.randint(0, w)
            y2 = random.randint(0, h)

            r = random.randint(0, 200)
            g = random.randint(0, 200)
            b = random.randint(0, 200)

            draw.line([(x1, y1), (x2, y2)], fill=(r, g, b), width=self.thickness)

        return img


class DotNoise:
    def __init__(self, dot_count: int = 50):
        self.dot_count = dot_count

    def apply(self, img: Image.Image) -> Image.Image:
        draw = ImageDraw.Draw(img)
        w, h = img.size

        for _ in range(self.dot_count):
            x = random.randint(0, w - 1)
            y = random.randint(0, h - 1)
            r = random.randint(1, 3)

            color = (random.randint(0, 200), random.randint(0, 200), random.randint(0, 200))
            draw.ellipse([(x - r, y - r), (x + r, y + r)], fill=color)

        return img


class ArcNoise:
    def __init__(self, arc_count: int = 3):
        self.arc_count = arc_count

    def apply(self, img: Image.Image) -> Image.Image:
        draw = ImageDraw.Draw(img)
        w, h = img.size

        for _ in range(self.arc_count):
            ax = random.randint(-w // 4, w)
            ay = random.randint(-h // 4, h)
            bx = random.randint(0, w + w // 4)
            by = random.randint(0, h + h // 4)
            x0, x1 = min(ax, bx), max(ax, bx)
            y0, y1 = min(ay, by), max(ay, by)

            color = (random.randint(0, 180), random.randint(0, 180), random.randint(0, 180))
            start_angle = random.randint(0, 360)
            end_angle = start_angle + random.randint(30, 180)

            draw.arc([(x0, y0), (x1, y1)], start_angle, end_angle, fill=color, width=2)

        return img


class NoisePipeline:
    def __init__(self, config: NoiseConfig = None):
        self.config = config or NoiseConfig()

    def apply_all(self, img: Image.Image, level: int = 1) -> Image.Image:
        scale = level / 3.0

        if random.random() < 0.8:
            img = GaussianNoise(sigma=self.config.gaussian_sigma * scale).apply(img)

        if random.random() < 0.5:
            img = SaltPepperNoise(amount=self.config.salt_pepper_amount * scale).apply(img)

        if random.random() < 0.3:
            img = SpeckleNoise(amount=self.config.speckle_amount * scale).apply(img)

        if random.random() < 0.7:
            count = max(1, int(self.config.line_count * scale))
            img = LineNoise(line_count=count, thickness=self.config.line_thickness).apply(img)

        if random.random() < 0.6:
            count = max(5, int(self.config.dot_count * scale))
            img = DotNoise(dot_count=count).apply(img)

        if random.random() < 0.4:
            count = max(1, int(self.config.arc_count * scale))
            img = ArcNoise(arc_count=count).apply(img)

        if self.config.blur_sigma > 0 and random.random() < 0.3:
            img = img.filter(ImageFilter.GaussianBlur(radius=self.config.blur_sigma * scale))

        return img
