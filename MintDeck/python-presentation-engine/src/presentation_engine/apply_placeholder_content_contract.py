"""Integrate placeholder content-limit enforcement into PlaceholderBuilder.

Run from the python-presentation-engine project root:

    python .\apply_placeholder_content_contract.py

The script modifies only:
    src/presentation_engine/builders/placeholder_builder.py

A .bak copy is created before the first modification. The patch is idempotent.
"""

from __future__ import annotations

import shutil
from pathlib import Path


TARGET = Path("src/presentation_engine/builders/placeholder_builder.py")
BACKUP = TARGET.with_suffix(".py.content-contract.bak")


def require_once(text: str, needle: str, description: str) -> None:
    count = text.count(needle)
    if count != 1:
        raise RuntimeError(
            f"Expected exactly one {description}; found {count}. No changes written."
        )


def main() -> int:
    if not TARGET.exists():
        raise FileNotFoundError(TARGET)

    text = TARGET.read_text(encoding="utf8")
    original = text

    layout_import = (
        "from presentation_engine.services.text_box_layout import TextBoxLayoutPolicy\n"
    )
    require_once(text, layout_import, "TextBoxLayoutPolicy import")

    content_import = (
        "from presentation_engine.services.placeholder_content_limits import (\n"
        "    PlaceholderContentLimitPolicy,\n"
        "    PlaceholderContentOverflowError,\n"
        ")\n"
    )
    if "PlaceholderContentLimitPolicy" not in text:
        text = text.replace(layout_import, layout_import + content_import, 1)

    layout_field = (
        "    text_box_layout_policy: TextBoxLayoutPolicy = field(\n"
        "        default_factory=TextBoxLayoutPolicy\n"
        "    )\n"
    )
    require_once(text, layout_field, "text-box policy field")

    content_field = (
        "    content_limit_policy: PlaceholderContentLimitPolicy = field(\n"
        "        default_factory=PlaceholderContentLimitPolicy\n"
        "    )\n"
    )
    if "content_limit_policy: PlaceholderContentLimitPolicy" not in text:
        text = text.replace(layout_field, layout_field + content_field, 1)

    fill_call = (
        "            self._fill_text_placeholder(\n"
        "                slide,\n"
        "                archetype,\n"
        "                definition,\n"
        "                text,\n"
        "                filled_idx,\n"
        "                report,\n"
        "            )\n"
    )
    require_once(text, fill_call, "text-placeholder fill call")

    validation_call = (
        "            self._enforce_content_limit_before_render(\n"
        "                archetype,\n"
        "                definition,\n"
        "                text,\n"
        "            )\n\n"
    )
    if "self._enforce_content_limit_before_render(" not in text:
        text = text.replace(fill_call, validation_call + fill_call, 1)

    prepare_method = "    def _prepare_text_for_rendering(\n"
    require_once(text, prepare_method, "prepare-text method")

    enforcement_method = '''    def _enforce_content_limit_before_render(\n        self,\n        archetype: str,\n        definition: PlaceholderDefinition,\n        text: str,\n    ) -> None:\n        """Reject configured content overflow before any placeholder mutation."""\n\n        try:\n            self.content_limit_policy.validate_or_raise(\n                archetype,\n                definition.name,\n                text,\n            )\n        except PlaceholderContentOverflowError as exc:\n            raise PlaceholderValidationException(str(exc)) from exc\n\n'''
    if "def _enforce_content_limit_before_render(" not in text:
        text = text.replace(prepare_method, enforcement_method + prepare_method, 1)

    if text == original:
        print("No changes required; content contract is already integrated.")
        return 0

    if not BACKUP.exists():
        shutil.copy2(TARGET, BACKUP)
    TARGET.write_text(text, encoding="utf8")
    compile(text, str(TARGET), "exec")

    print(f"Updated: {TARGET}")
    print(f"Backup:  {BACKUP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
