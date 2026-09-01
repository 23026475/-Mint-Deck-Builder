from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path.cwd()

FILES_TO_CHECK = [
    "src/presentation_engine/handlers/image_handler.py",
    "src/presentation_engine/handlers/table_handler.py",
    "src/presentation_engine/handlers/media_handler.py",
    "src/presentation_engine/builders/placeholder_builder.py",
    "src/presentation_engine/handlers/__init__.py",
    "data/input/image_e2e_validation_contract.json",
    "data/input/table_e2e_validation_contract.json",
    "run_image_e2e_validation.py",
    "run_table_e2e_validation.py",
    "tests/unit/test_image_handler.py",
    "tests/unit/test_table_handler.py",
    "tests/integration/test_image_e2e_ooxml_package.py",
    "tests/integration/test_table_e2e_ooxml_package.py",
]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf8", errors="replace")


def print_section(title: str) -> None:
    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)


def show_file_presence() -> None:
    print_section("1. File presence")
    for relative in FILES_TO_CHECK:
        path = PROJECT_ROOT / relative
        status = "FOUND" if path.exists() else "MISSING"
        print(f"{status:8} {relative}")


def show_chart_mapping() -> None:
    print_section("2. PlaceholderBuilder chart mapping")
    path = PROJECT_ROOT / "src/presentation_engine/builders/placeholder_builder.py"
    if not path.exists():
        print("placeholder_builder.py not found")
        return

    text = read_text(path)
    match = re.search(r'"chart"\s*:\s*\[(.*?)\n\s*\],', text, flags=re.S)
    if not match:
        print("Could not find chart mapping block.")
        return

    block = match.group(0)
    print(block)

    expected_tokens = [
        'PlaceholderDefinition("chart", 10, "fields.chart"',
        'content_type="chart"',
        'PlaceholderDefinition("lead_in", 13, "fields.lead_in"',
        'PlaceholderDefinition("takeaway", 14, "fields.takeaway"',
    ]

    print("\nExpected chart mapping checks:")
    for token in expected_tokens:
        print(f"{'OK' if token in block else 'MISSING':8} {token}")


def show_media_handler_pattern() -> None:
    print_section("3. MediaHandler processor registration pattern")
    path = PROJECT_ROOT / "src/presentation_engine/handlers/media_handler.py"
    if not path.exists():
        print("media_handler.py not found")
        return

    text = read_text(path)
    indicators = [
        "ImageMediaProcessor",
        "TableMediaProcessor",
        "processors:",
        "default_factory",
        "ImageHandler",
        "TableHandler",
        "ChartHandler",
        "ChartMediaProcessor",
    ]
    for indicator in indicators:
        print(f"{'FOUND' if indicator in text else 'MISSING':8} {indicator}")

    print("\nRelevant MediaHandler lines:")
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        if any(token in line for token in ["Processor", "processors", "ImageHandler", "TableHandler", "ChartHandler"]):
            print(f"{index:4}: {line}")


def show_handler_conventions() -> None:
    print_section("4. Handler conventions")
    for relative in [
        "src/presentation_engine/handlers/image_handler.py",
        "src/presentation_engine/handlers/table_handler.py",
    ]:
        path = PROJECT_ROOT / relative
        if not path.exists():
            print(f"MISSING {relative}")
            continue

        text = read_text(path)
        print(f"\n{relative}")
        for token in ["class", "Exception", "process(", "insert_", "_collect", "_normalize", "_placeholder_by_idx"]:
            count = text.count(token)
            print(f"  {token:20} {count}")

        class_names = re.findall(r"^class\s+(\w+)", text, flags=re.M)
        print(f"  classes: {', '.join(class_names)}")


def show_e2e_patterns() -> None:
    print_section("5. Existing E2E validation patterns")
    for relative in ["run_image_e2e_validation.py", "run_table_e2e_validation.py"]:
        path = PROJECT_ROOT / relative
        if not path.exists():
            print(f"MISSING {relative}")
            continue

        text = read_text(path)
        print(f"\n{relative}")
        for token in ["DeckBuilder", "zipfile", "ElementTree", "duplicate_zip_entries", "overall_status", "REPORT_PATH", "CONTRACT_PATH"]:
            print(f"  {'FOUND' if token in text else 'MISSING':8} {token}")


def show_git_status_hint() -> None:
    print_section("6. Next manual checks")
    print("Run these after reviewing this report:")
    print('  git --no-pager status --short')
    print('  python -m unittest discover -s ".\\tests" -p "test_*.py"')
    print('  python ".\\run_table_e2e_validation.py"')
    print("\nIf all are healthy, proceed to create ChartHandler in:")
    print('  src/presentation_engine/handlers/chart_handler.py')
    print('  tests/unit/test_chart_handler.py')
    print('  data/input/chart_e2e_validation_contract.json')
    print('  run_chart_e2e_validation.py')
    print('  tests/integration/test_chart_e2e_ooxml_package.py')


def main() -> int:
    print(f"Project root: {PROJECT_ROOT}")
    show_file_presence()
    show_chart_mapping()
    show_media_handler_pattern()
    show_handler_conventions()
    show_e2e_patterns()
    show_git_status_hint()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
