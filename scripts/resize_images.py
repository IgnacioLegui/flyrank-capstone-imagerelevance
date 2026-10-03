"""Resize the downloaded corpus so it stays a few MB, and create the CREDITS.md template.

Usage (from the repo root):
    .venv\\Scripts\\python scripts/resize_images.py

- The expected filenames come from data/SHOTLIST.md (single source of truth: the `xxx_NN.jpg`
  names in backticks), so this script never drifts from the shot list.
- For each expected name it looks in data/raw/ for a file with the same stem and any image
  extension, then writes data/images/<name>.jpg: longest side 1024 px, JPEG quality 80.
- EXIF metadata (camera info, GPS) is dropped. The EXIF rotation is applied first, so
  phone photos don't end up sideways.
- data/images/CREDITS.md gets one row per image. Existing rows are never overwritten, so
  re-running is safe after you've filled in URLs and photographers.

Exit code 1 if any expected image is missing (the ones present are still processed).
"""

import argparse
import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `app.` imports work when run as a plain script

from app.domain.taxonomy import SubjectKey  # noqa: E402

MAX_SIDE = 1024
JPEG_QUALITY = 80
RAW_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
SHOTLIST_NAME = re.compile(r"`([a-z_]+)_(\d{2})\.jpg`")
CREDITS_HEADER = (
    "# Image credits\n\n"
    "All images are from Unsplash or Pexels under their free licenses.\n\n"
    "| File | Source URL | Photographer |\n"
    "|---|---|---|\n"
)


def expected_names(shotlist: Path) -> list[str]:
    """Filenames (without extension) listed in the shot list, in order, e.g. 'red_fox_01'."""
    allowed_prefixes = {key.value for key in SubjectKey if key is not SubjectKey.OTHER} | {"ambiguous"}
    names = []
    for prefix, number in SHOTLIST_NAME.findall(shotlist.read_text(encoding="utf-8")):
        if prefix not in allowed_prefixes:
            sys.exit(f"Shot list uses prefix '{prefix}', which is not a taxonomy subject key")
        names.append(f"{prefix}_{number}")
    if len(names) != len(set(names)):
        sys.exit("Shot list contains duplicate filenames")
    return names


def resize(src: Path, dest: Path) -> None:
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)  # apply camera rotation before EXIF is dropped
        img = img.convert("RGB")            # PNG/WebP may have alpha; JPEG can't
        img.thumbnail((MAX_SIDE, MAX_SIDE))  # keeps aspect ratio, only ever shrinks
        img.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True)  # no exif= -> metadata dropped


def update_credits(credits: Path, filenames: list[str]) -> int:
    """Add a row for every filename not yet in CREDITS.md. Returns how many rows were added."""
    text = credits.read_text(encoding="utf-8") if credits.exists() else CREDITS_HEADER
    new_rows = [f"| {name} |  |  |\n" for name in filenames if f"| {name} |" not in text]
    if not text.endswith("\n"):
        text += "\n"
    credits.write_text(text + "".join(new_rows), encoding="utf-8")
    return len(new_rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "images")
    parser.add_argument("--shotlist", type=Path, default=ROOT / "data" / "SHOTLIST.md")
    args = parser.parse_args()

    names = expected_names(args.shotlist)
    args.out.mkdir(parents=True, exist_ok=True)
    raw_files = {
        p.stem.lower(): p
        for p in (args.raw.iterdir() if args.raw.exists() else [])
        if p.suffix.lower() in RAW_EXTENSIONS
    }

    done, missing = [], []
    for name in names:
        src = raw_files.get(name)
        if src is None:
            missing.append(name)
            continue
        resize(src, args.out / f"{name}.jpg")
        done.append(f"{name}.jpg")

    unexpected = sorted(set(raw_files) - set(names))
    added = update_credits(args.out / "CREDITS.md", done)
    total_mb = sum((args.out / f).stat().st_size for f in done) / 1_048_576

    print(f"Resized {len(done)}/{len(names)} images -> {args.out} ({total_mb:.1f} MB)")
    print(f"CREDITS.md: {added} new row(s) added")
    if unexpected:
        print(f"Ignored {len(unexpected)} file(s) in raw/ not in the shot list: {', '.join(unexpected)}")
    if missing:
        print(f"MISSING {len(missing)}: {', '.join(missing)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
