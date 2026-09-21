#!/usr/bin/env python3
"""Download OFL handwriting fonts from the google/fonts GitHub repo into data/fonts/.

Every font is verified to load with Pillow before being kept.
"""
import sys
import urllib.request
from pathlib import Path

from PIL import ImageFont

FONTS_DIR = Path(__file__).resolve().parent.parent / "data" / "fonts"
BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl"

# filename -> path inside ofl/
FONTS = {
    "Caveat.ttf": "caveat/Caveat%5Bwght%5D.ttf",
    "HomemadeApple.ttf": "homemadeapple/HomemadeApple-Regular.ttf",
    "ShadowsIntoLight.ttf": "shadowsintolight/ShadowsIntoLight-Regular.ttf",
    "Kalam.ttf": "kalam/Kalam-Regular.ttf",
    "IndieFlower.ttf": "indieflower/IndieFlower-Regular.ttf",
    "NothingYouCouldDo.ttf": "nothingyoucoulddo/NothingYouCouldDo-Regular.ttf",
    "ReenieBeanie.ttf": "reeniebeanie/ReenieBeanie.ttf",
    "SueEllenFrancisco.ttf": "sueellenfrancisco/SueEllenFrancisco-Regular.ttf",
    "NanumPenScript.ttf": "nanumpenscript/NanumPenScript-Regular.ttf",
    "LaBelleAurore.ttf": "labelleaurore/LaBelleAurore-Regular.ttf",
    "CedarvilleCursive.ttf": "cedarvillecursive/Cedarville-Cursive.ttf",
    "Kristi.ttf": "kristi/Kristi-Regular.ttf",
}


def main() -> int:
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    ok, failed = 0, []
    for name, rel in FONTS.items():
        dest = FONTS_DIR / name
        if dest.exists() and dest.stat().st_size > 10_000:
            print(f"skip  {name} (exists)")
            ok += 1
            continue
        url = f"{BASE}/{rel}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "WriteUP-setup"})
            data = urllib.request.urlopen(req, timeout=30).read()
            dest.write_bytes(data)
            # verify loadable
            font = ImageFont.truetype(str(dest), 32)
            font.getbbox("Handwriting test 123")
            print(f"ok    {name} ({len(data)//1024} KB)")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL  {name}: {exc}")
            dest.unlink(missing_ok=True)
            failed.append(name)
    print(f"\n{ok} fonts ready, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
