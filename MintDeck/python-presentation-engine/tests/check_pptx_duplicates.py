from __future__ import annotations

import sys
import zipfile
from collections import Counter
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python check_pptx_duplicates.py <pptx-path>")

    pptx_path = Path(sys.argv[1])

    if not pptx_path.exists():
        raise SystemExit(f"File not found: {pptx_path}")

    with zipfile.ZipFile(pptx_path, "r") as archive:
        names = archive.namelist()

    counts = Counter(names)
    duplicates = {name: count for name, count in counts.items() if count > 1}

    print(f"PPTX: {pptx_path}")
    print(f"Total ZIP entries: {len(names)}")
    print(f"Duplicate entries: {len(duplicates)}")

    if duplicates:
        print("FAILED: Duplicate ZIP entries found.")
        for name, count in sorted(duplicates.items()):
            print(f"{count}x {name}")
        raise SystemExit(1)

    print("PASS: No duplicate ZIP entries found.")


if __name__ == "__main__":
    main()
