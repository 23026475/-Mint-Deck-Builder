from pathlib import Path
from PIL import Image

image_dir = Path(r".\data\assets\images")
supported = {".jpg", ".jpeg", ".png"}

good = []
bad = []

for path in image_dir.iterdir():
    if not path.is_file():
        continue

    if path.suffix.lower() not in supported:
        continue

    try:
        with Image.open(path) as img:
            img.verify()
        good.append(path.name)
    except Exception as exc:
        bad.append((path.name, str(exc)))

print("GOOD IMAGES:")
for name in good[:30]:
    print("  " + name)

print()
print(f"Good count: {len(good)}")
print(f"Bad count: {len(bad)}")

if bad:
    print()
    print("BAD IMAGES:")
    for name, error in bad[:30]:
        print(f"  {name} -> {error}")
