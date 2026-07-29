import os
import sys
import math
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from typing import Optional, Tuple, List
from dataclasses import dataclass


@dataclass
class DistortionConfig:
    wave_amplitude: float = 3.0
    wave_frequency: float = 0.05
    swirl_strength: float = 0.3
    swirl_radius: float = 100.0
    perspective_strength: float = 0.1
    rotate_range: Tuple[float, float] = (-5.0, 5.0)
    scale_range: Tuple[float, float] = (0.9, 1.1)
    shear_range: Tuple[float, float] = (-0.05, 0.05)


class WaveDistortion:
    def __init__(self, amplitude: float = 3.0, frequency: float = 0.05):
        self.amplitude = amplitude
        self.frequency = frequency

    def apply(self, img: Image.Image) -> Image.Image:
        arr = np.array(img)
        h, w = arr.shape[:2]
        result = np.zeros_like(arr)

        y_coords = np.arange(h).reshape(-1, 1)
        x_coords = np.arange(w).reshape(1, -1)

        x_offset = (self.amplitude * np.sin(y_coords * self.frequency)).astype(int)
        y_offset = (self.amplitude * np.cos(x_coords * self.frequency * 0.7)).astype(int)

        for c in range(arr.shape[2] if len(arr.shape) > 2 else 1):
            if len(arr.shape) == 3:
                src_y = np.clip(y_coords + y_offset, 0, h - 1)
                src_x = np.clip(x_coords + x_offset, 0, w - 1)
                result[:, :, c] = arr[src_y, src_x, c]
            else:
                src_y = np.clip(y_coords + y_offset, 0, h - 1)
                src_x = np.clip(x_coords + x_offset, 0, w - 1)
                result = arr[src_y, src_x]

        return Image.fromarray(result)


class SwirlDistortion:
    def __init__(self, strength: float = 0.3, radius: float = 100.0):
        self.strength = strength
        self.radius = radius

    def apply(self, img: Image.Image) -> Image.Image:
        arr = np.array(img)
        h, w = arr.shape[:2]
        cx, cy = w / 2, h / 2

        y_coords = np.arange(h).reshape(-1, 1).astype(np.float32)
        x_coords = np.arange(w).reshape(1, -1).astype(np.float32)

        dx = x_coords - cx
        dy = y_coords - cy
        dist = np.sqrt(dx ** 2 + dy ** 2)
        angle = np.arctan2(dy, dx)

        swirl_angle = angle + self.strength * np.exp(-dist ** 2 / (2 * self.radius ** 2))

        new_x = (cx + dist * np.cos(swirl_angle)).astype(np.float32)
        new_y = (cy + dist * np.sin(swirl_angle)).astype(np.float32)

        new_x = np.clip(new_x, 0, w - 1)
        new_y = np.clip(new_y, 0, h - 1)

        result = np.zeros_like(arr)
        for c in range(arr.shape[2] if len(arr.shape) > 2 else 1):
            if len(arr.shape) == 3:
                result[:, :, c] = arr[new_y.astype(int), new_x.astype(int), c]
            else:
                result = arr[new_y.astype(int), new_x.astype(int)]

        return Image.fromarray(result)


class PerspectiveDistortion:
    def __init__(self, strength: float = 0.1):
        self.strength = strength

    def apply(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        s = self.strength

        coeffs = [
            random.uniform(-s, s) * w, random.uniform(-s, s) * h,
            w + random.uniform(-s, s) * w, random.uniform(-s, s) * h,
            random.uniform(-s, s) * w, h + random.uniform(-s, s) * h,
            w + random.uniform(-s, s) * w, h + random.uniform(-s, s) * h,
        ]

        coeffs[0] = max(0, coeffs[0])
        coeffs[1] = max(0, coeffs[1])
        coeffs[2] = min(w, coeffs[2])
        coeffs[3] = max(0, coeffs[3])
        coeffs[4] = max(0, coeffs[4])
        coeffs[5] = min(h, coeffs[5])
        coeffs[6] = min(w, coeffs[6])
        coeffs[7] = min(h, coeffs[7])

        return img.transform(img.size, Image.PERSPECTIVE, coeffs, Image.BICUBIC)


class ElasticDistortion:
    def __init__(self, alpha: float = 40.0, sigma: float = 5.0):
        self.alpha = alpha
        self.sigma = sigma

    def apply(self, img: Image.Image) -> Image.Image:
        arr = np.array(img)
        h, w = arr.shape[:2]

        dx = np.random.randn(h, w).astype(np.float32) * self.alpha
        dy = np.random.randn(h, w).astype(np.float32) * self.alpha

        from scipy.ndimage import gaussian_filter
        dx = gaussian_filter(dx, self.sigma)
        dy = gaussian_filter(dy, self.sigma)

        y_coords = np.arange(h).reshape(-1, 1) + dy
        x_coords = np.arange(w).reshape(1, -1) + dx

        y_coords = np.clip(y_coords, 0, h - 1).astype(int)
        x_coords = np.clip(x_coords, 0, w - 1).astype(int)

        result = arr[y_coords, x_coords]
        return Image.fromarray(result)


class DistortionPipeline:
    def __init__(self, config: DistortionConfig = None):
        self.config = config or DistortionConfig()

    def apply_all(self, img: Image.Image) -> Image.Image:
        if random.random() < 0.7:
            img = WaveDistortion(
                amplitude=self.config.wave_amplitude,
                frequency=self.config.wave_frequency,
            ).apply(img)

        if random.random() < 0.4:
            img = SwirlDistortion(
                strength=self.config.swirl_strength,
                radius=self.config.swirl_radius,
            ).apply(img)

        if random.random() < 0.3:
            img = PerspectiveDistortion(
                strength=self.config.perspective_strength,
            ).apply(img)

        return img

    def apply_transform(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        angle = random.uniform(*self.config.rotate_range)
        scale = random.uniform(*self.config.scale_range)
        shear = random.uniform(*self.config.shear_range)

        img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(255, 255, 255))

        new_w = int(w * scale)
        new_h = int(h * scale)
        img = img.resize((new_w, new_h), Image.BICUBIC)

        if new_w != w or new_h != h:
            padded = Image.new("RGB", (w, h), (255, 255, 255))
            offset_x = (w - new_w) // 2
            offset_y = (h - new_h) // 2
            padded.paste(img, (offset_x, offset_y))
            img = padded

        return img
