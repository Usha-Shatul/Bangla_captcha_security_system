import os
import sys
import urllib.request
import zipfile
import shutil
from typing import List


FONT_DIR = os.path.join(os.path.dirname(__file__), "bangla_font")

FREE_BANGLA_FONTS = {
    "NotoSansBengali": {
        "url": "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansBengali/NotoSansBengali-Regular.ttf",
        "filename": "NotoSansBengali-Regular.ttf",
    },
    "NotoSerifBengali": {
        "url": "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSerifBengali/NotoSerifBengali-Regular.ttf",
        "filename": "NotoSerifBengali-Regular.ttf",
    },
    "SolaimanLipi": {
        "url": "https://github.com/AcademySoftwareFoundation/openexr/raw/main/share/ci/scripts/windows/solaiman-lipi/SolaimanLipi_20-04-045.ttf",
        "filename": "SolaimanLipi.ttf",
    },
}

SIMPLE_BANGLA_CHARS = [
    "অ", "আ", "ই", "ঈ", "উ", "ঊ", "ঋ", "এ", "ঐ", "ও", "ঔ",
    "ক", "খ", "গ", "ঘ", "ঙ", "চ", "ছ", "জ", "ঝ", "ঞ",
    "ট", "ঠ", "ড", "ঢ", "ণ", "ত", "থ", "দ", "ধ", "ন",
    "প", "ফ", "ব", "ভ", "ম", "য", "র", "ল", "শ", "ষ", "স", "হ",
    "া", "ি", "ী", "ু", "ূ", "ৃ", "ে", "ৈ", "ো", "ৌ",
    "্", "ং", "ঃ", "ঁ",
    "০", "১", "২", "৩", "৪", "৫", "৬", "৭", "৮", "৯",
]


def download_font(name: str, info: dict, target_dir: str) -> bool:
    target_path = os.path.join(target_dir, info["filename"])

    if os.path.isfile(target_path):
        print(f"  [skip] {info['filename']} already exists")
        return True

    try:
        print(f"  [download] {name}...")
        urllib.request.urlretrieve(info["url"], target_path)
        print(f"  [ok] {info['filename']}")
        return True
    except Exception as e:
        print(f"  [fail] {name}: {e}")
        return False


def download_all_fonts(target_dir: str = None) -> dict:
    target_dir = target_dir or FONT_DIR
    os.makedirs(target_dir, exist_ok=True)

    results = {"success": [], "failed": []}

    print("Downloading free Bangla fonts...")
    print(f"Target: {target_dir}\n")

    for name, info in FREE_BANGLA_FONTS.items():
        if download_font(name, info, target_dir):
            results["success"].append(name)
        else:
            results["failed"].append(name)

    print(f"\nDone: {len(results['success'])} downloaded, {len(results['failed'])} failed")
    return results


def list_installed_fonts(font_dir: str = None) -> List[str]:
    font_dir = font_dir or FONT_DIR
    if not os.path.isdir(font_dir):
        return []

    fonts = []
    for fname in sorted(os.listdir(font_dir)):
        if fname.lower().endswith((".ttf", ".otf", ".ttc")):
            fonts.append(fname)
    return fonts


def create_sample_word_files(output_dir: str = None):
    output_dir = output_dir or os.path.join(os.path.dirname(__file__), "word_dataset")
    os.makedirs(output_dir, exist_ok=True)

    transport_words = [
        "রেল", "বাস", "ট্রেন", "টিকিট", "বুকিং", "যাত্রী", "স্টেশন",
        "প্লাটফর্ম", "গন্তব্য", "ভ্রমণ", "যাতায়াত", "রিজার্ভ", "ভাড়া",
        "সময়সূচী", "আসন", "জানালা", "দরজা", "পানি", "খাবার", "চা",
    ]

    common_words = [
        "বাংলা", "ক্যাপচা", "নিরাপত্তা", "যাচাই", "প্রমাণ",
        "স্বাগতম", "ধন্যবাদ", "নমস্কার", "শুভেচ্ছা", "অভিনন্দন",
        "সংবাদ", "সাইট", "ওয়েব", "ইন্টারনেট", "কম্পিউটার",
    ]

    files = {
        "transport.txt": transport_words,
        "common.txt": common_words,
    }

    for fname, words in files.items():
        fpath = os.path.join(output_dir, fname)
        if not os.path.isfile(fpath):
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(words))
            print(f"Created: {fpath}")

    all_words = transport_words + common_words
    all_path = os.path.join(output_dir, "all_words.txt")
    if not os.path.isfile(all_path):
        with open(all_path, "w", encoding="utf-8") as f:
            f.write("\n".join(all_words))
        print(f"Created: {all_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Bangla font utilities")
    parser.add_argument("--download", action="store_true", help="Download free Bangla fonts")
    parser.add_argument("--list", action="store_true", help="List installed fonts")
    parser.add_argument("--words", action="store_true", help="Create sample word dataset files")
    parser.add_argument("--dir", type=str, default=None, help="Custom font directory")
    args = parser.parse_args()

    if args.download:
        download_all_fonts(args.dir)
    elif args.list:
        fonts = list_installed_fonts(args.dir)
        if fonts:
            print("Installed fonts:")
            for f in fonts:
                print(f"  - {f}")
        else:
            print("No fonts found. Run: python font_utils.py --download")
    elif args.words:
        create_sample_word_files()
    else:
        parser.print_help()
