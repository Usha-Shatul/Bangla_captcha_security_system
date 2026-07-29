import os
import sys
import glob
import shutil
import urllib.request
from typing import List, Optional


FONT_DIR = os.path.join(os.path.dirname(__file__), "bangla_font")

WINDOWS_FONT_DIRS = [
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"),
    os.path.expanduser("~\\AppData\\Local\\Microsoft\\Windows\\Fonts"),
]

BANGLA_FONT_NAMES = [
    "NotoSansBengali", "NotoSerifBengali", "SolaimanLipi",
    "Kalpurush", "SiyamRupali", "Vrinda", "ShonarBangla",
    "Atma", "BalooDa2", "HindSiliguri", "TiroBangla",
    "NotoSansBengaliUI", "NotoSerifBengaliUI",
]

FONT_SOURCES = [
    {
        "name": "NotoSansBengali-Regular",
        "url": "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSansBengali/NotoSansBengali-Regular.ttf",
    },
    {
        "name": "NotoSansBengali-Bold",
        "url": "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSansBengali/NotoSansBengali-Bold.ttf",
    },
    {
        "name": "NotoSerifBengali-Regular",
        "url": "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSerifBengali/NotoSerifBengali-Regular.ttf",
    },
    {
        "name": "NotoSansBengali-ExtraBold",
        "url": "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSansBengali/NotoSansBengali-ExtraBold.ttf",
    },
]


def find_system_bangla_fonts() -> List[str]:
    found = []
    for font_dir in WINDOWS_FONT_DIRS:
        if not os.path.isdir(font_dir):
            continue
        for fname in os.listdir(font_dir):
            if not fname.lower().endswith((".ttf", ".otf", ".ttc")):
                continue
            name_lower = fname.lower()
            for bangla_name in BANGLA_FONT_NAMES:
                if bangla_name.lower() in name_lower:
                    found.append(os.path.join(font_dir, fname))
                    break
    return found


def find_all_system_fonts() -> List[str]:
    all_fonts = []
    for font_dir in WINDOWS_FONT_DIRS:
        if not os.path.isdir(font_dir):
            continue
        for fname in os.listdir(font_dir):
            if fname.lower().endswith((".ttf", ".otf")):
                all_fonts.append(os.path.join(font_dir, fname))
    return all_fonts


def test_font_bangla_support(font_path: str) -> bool:
    try:
        from PIL import ImageFont, Image, ImageDraw
        font = ImageFont.truetype(font_path, 36)
        img = Image.new("RGB", (200, 50), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((10, 5), "বাংলা", font=font, fill=(0, 0, 0))
        pixels = list(img.getdata())
        non_white = sum(1 for p in pixels if p != (255, 255, 255))
        return non_white > 50
    except Exception:
        return False


def download_font(source: dict, target_dir: str) -> bool:
    target_path = os.path.join(target_dir, f"{source['name']}.ttf")

    if os.path.isfile(target_path):
        print(f"  [exists] {source['name']}.ttf")
        return True

    try:
        print(f"  [downloading] {source['name']}...")
        req = urllib.request.Request(source["url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
        with open(target_path, "wb") as f:
            f.write(data)
        size_kb = len(data) / 1024
        print(f"  [ok] {source['name']}.ttf ({size_kb:.0f} KB)")
        return True
    except Exception as e:
        print(f"  [fail] {source['name']}: {e}")
        return False


def copy_system_font(font_path: str, target_dir: str) -> str:
    fname = os.path.basename(font_path)
    target = os.path.join(target_dir, fname)
    if not os.path.isfile(target):
        shutil.copy2(font_path, target)
        print(f"  [copied] {fname}")
    return target


def setup_fonts() -> dict:
    os.makedirs(FONT_DIR, exist_ok=True)

    result = {"fonts": [], "source": []}

    existing = [f for f in os.listdir(FONT_DIR) if f.lower().endswith((".ttf", ".otf", ".ttc"))]
    if existing:
        print(f"Found {len(existing)} existing font(s) in bangla_font/:")
        for f in existing:
            print(f"  - {f}")
            result["fonts"].append(os.path.join(FONT_DIR, f))
        return result

    print("No fonts found. Searching system...")
    system_fonts = find_system_bangla_fonts()
    if system_fonts:
        print(f"Found {len(system_fonts)} Bangla font(s) in system:")
        for fp in system_fonts:
            copied = copy_system_font(fp, FONT_DIR)
            result["fonts"].append(copied)
            result["source"].append(fp)
        return result

    print("No system Bangla fonts found. Trying all system fonts...")
    all_fonts = find_all_system_fonts()
    for fp in all_fonts[:20]:
        if test_font_bangla_support(fp):
            print(f"  [supports Bangla] {os.path.basename(fp)}")
            copied = copy_system_font(fp, FONT_DIR)
            result["fonts"].append(copied)
            break

    if not result["fonts"]:
        print("\nDownloading Noto Bengali fonts from Google...")
        for source in FONT_SOURCES:
            if download_font(source, FONT_DIR):
                result["fonts"].append(os.path.join(FONT_DIR, f"{source['name']}.ttf"))

    return result


def get_any_font(size: int = 36):
    from PIL import ImageFont

    fonts_in_dir = [
        os.path.join(FONT_DIR, f)
        for f in os.listdir(FONT_DIR)
        if f.lower().endswith((".ttf", ".otf", ".ttc"))
    ] if os.path.isdir(FONT_DIR) else []

    for fp in fonts_in_dir:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue

    system_bangla = find_system_bangla_fonts()
    for fp in system_bangla:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue

    all_system = find_all_system_fonts()
    for fp in all_system:
        try:
            font = ImageFont.truetype(fp, size)
            if test_font_bangla_support(fp):
                return font
        except Exception:
            continue

    for name in ["arial.ttf", "Arial.ttf", "times.ttf", "Times.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue

    print("WARNING: No suitable font found. Using default font.")
    return ImageFont.load_default()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Setup Bangla fonts for CAPTCHA")
    parser.add_argument("--setup", action="store_true", help="Auto-detect and install fonts")
    parser.add_argument("--test", action="store_true", help="Test which fonts support Bangla")
    parser.add_argument("--list", action="store_true", help="List all fonts in bangla_font/")
    args = parser.parse_args()

    if args.setup:
        print("=" * 50)
        print("Bangla Font Setup")
        print("=" * 50)
        result = setup_fonts()
        print(f"\nResult: {len(result['fonts'])} font(s) available")

    elif args.test:
        print("Testing system fonts for Bangla support...\n")
        for fp in find_all_system_fonts()[:30]:
            name = os.path.basename(fp)
            if test_font_bangla_support(fp):
                print(f"  [OK] {name}")
            else:
                print(f"  [--] {name}")

    elif args.list:
        fonts = [f for f in os.listdir(FONT_DIR) if f.lower().endswith((".ttf", ".otf", ".ttc"))] if os.path.isdir(FONT_DIR) else []
        if fonts:
            print("Fonts in bangla_font/:")
            for f in fonts:
                size = os.path.getsize(os.path.join(FONT_DIR, f))
                print(f"  {f} ({size / 1024:.0f} KB)")
        else:
            print("No fonts found. Run: python font_setup.py --setup")

    else:
        parser.print_help()
