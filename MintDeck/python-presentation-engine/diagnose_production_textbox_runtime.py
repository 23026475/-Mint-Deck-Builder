"""Trace the exact TextBoxLayoutPolicy.apply() used by the production build.

Diagnostic only. This script does not modify production source files.
It runs the existing DeckBuilder in the same Python process in which runtime
module identity, source, hash, setter execution, and final xfrm are captured.

Run from the python-presentation-engine project root:

    $env:PYTHONPATH = ".\\src"
    python .\\diagnose_production_textbox_runtime.py

Outputs:

    data/output/production_textbox_runtime_diagnostic.json
    data/output/production_textbox_runtime_diagnostic.md
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import platform
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pptx.oxml.ns import qn

from presentation_engine.builders.deck_builder import DeckBuilder
import presentation_engine.services.text_box_layout as text_box_layout_module
from presentation_engine.services.text_box_layout import TextBoxLayoutPolicy


EMU_PER_INCH = 914400
TARGETS = {
    ("statement", "support"): {"slide_number": 2, "idx": 2},
    ("image_right", "body"): {"slide_number": 6, "idx": 12},
    ("closing", "steps"): {"slide_number": 8, "idx": 12},
}


@dataclass
class RuntimeState:
    slide_number: int
    idx: int
    archetype: str
    placeholder_name: str
    event: str
    reached: bool
    assigned_value: int | float | str | None
    assigned_type: str | None
    left: int | None
    top: int | None
    width: int | None
    height: int | None
    width_inches: float | None
    height_inches: float | None
    xfrm_exists: bool
    off_x: int | None
    off_y: int | None
    ext_cx: int | None
    ext_cy: int | None
    xfrm_xml: str | None
    sppr_xml: str | None


class TracedGeometryValue:
    """Proxy exposing shape geometry while logging assignments.

    This avoids editing TextBoxLayoutPolicy.apply(). The real method executes
    unchanged against this proxy. Geometry setters are forwarded to the real
    placeholder and captured immediately before and after each assignment.
    """

    def __init__(
        self,
        real_shape: Any,
        *,
        archetype: str,
        placeholder_name: str,
        target: dict[str, int],
        states: list[RuntimeState],
    ) -> None:
        object.__setattr__(self, "_real_shape", real_shape)
        object.__setattr__(self, "_archetype", archetype)
        object.__setattr__(self, "_placeholder_name", placeholder_name)
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_states", states)

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_real_shape"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return

        real_shape = object.__getattribute__(self, "_real_shape")
        if name in {"left", "top", "width", "height"}:
            self._capture(
                event=f"before_set_{name}",
                reached=True,
                assigned_value=value,
            )
            setattr(real_shape, name, value)
            self._capture(
                event=f"after_set_{name}",
                reached=True,
                assigned_value=value,
            )
            return

        setattr(real_shape, name, value)
        # Capture any later geometry/XML-touching operation performed by apply.
        if name in {"_element", "element", "spPr", "xfrm"}:
            self._capture(
                event=f"after_set_{name}",
                reached=True,
                assigned_value=repr(value),
            )

    def _capture(
        self,
        *,
        event: str,
        reached: bool,
        assigned_value: Any = None,
    ) -> None:
        states = object.__getattribute__(self, "_states")
        real_shape = object.__getattribute__(self, "_real_shape")
        archetype = object.__getattribute__(self, "_archetype")
        placeholder_name = object.__getattribute__(self, "_placeholder_name")
        target = object.__getattribute__(self, "_target")
        states.append(
            make_state(
                shape=real_shape,
                slide_number=target["slide_number"],
                idx=target["idx"],
                archetype=archetype,
                placeholder_name=placeholder_name,
                event=event,
                reached=reached,
                assigned_value=assigned_value,
            )
        )


def integer(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def inch(value: Any) -> float | None:
    resolved = integer(value)
    return None if resolved is None else round(resolved / EMU_PER_INCH, 4)


def shape_sppr(shape: Any) -> Any:
    return shape._element.spPr


def shape_xfrm(shape: Any) -> Any | None:
    return getattr(shape_sppr(shape), "xfrm", None)


def child_attr(parent: Any, tag: str, attr: str) -> int | None:
    if parent is None:
        return None
    child = parent.find(qn(tag))
    if child is None:
        return None
    return integer(child.get(attr))


def xml(element: Any) -> str | None:
    if element is None:
        return None
    try:
        return element.xml
    except AttributeError:
        return str(element)


def placeholder_idx(shape: Any) -> int | None:
    try:
        return int(shape.placeholder_format.idx)
    except (AttributeError, TypeError, ValueError):
        return None


def matching_layout_placeholder(shape: Any) -> Any | None:
    slide = getattr(getattr(shape, "part", None), "slide", None)
    if slide is None:
        return None
    idx = placeholder_idx(shape)
    for candidate in slide.slide_layout.placeholders:
        if placeholder_idx(candidate) == idx:
            return candidate
    return None


def make_state(
    *,
    shape: Any,
    slide_number: int,
    idx: int,
    archetype: str,
    placeholder_name: str,
    event: str,
    reached: bool,
    assigned_value: Any = None,
) -> RuntimeState:
    xfrm = shape_xfrm(shape)
    return RuntimeState(
        slide_number=slide_number,
        idx=idx,
        archetype=archetype,
        placeholder_name=placeholder_name,
        event=event,
        reached=reached,
        assigned_value=(
            integer(assigned_value)
            if isinstance(assigned_value, (int, float))
            else assigned_value
        ),
        assigned_type=(
            type(assigned_value).__name__
            if assigned_value is not None
            else None
        ),
        left=integer(getattr(shape, "left", None)),
        top=integer(getattr(shape, "top", None)),
        width=integer(getattr(shape, "width", None)),
        height=integer(getattr(shape, "height", None)),
        width_inches=inch(getattr(shape, "width", None)),
        height_inches=inch(getattr(shape, "height", None)),
        xfrm_exists=xfrm is not None,
        off_x=child_attr(xfrm, "a:off", "x"),
        off_y=child_attr(xfrm, "a:off", "y"),
        ext_cx=child_attr(xfrm, "a:ext", "cx"),
        ext_cy=child_attr(xfrm, "a:ext", "cy"),
        xfrm_xml=xml(xfrm),
        sppr_xml=xml(shape_sppr(shape)),
    )


def source_hash(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def repository_matches(project_root: Path) -> dict[str, list[dict[str, Any]]]:
    definitions: list[dict[str, Any]] = []
    imports: list[dict[str, Any]] = []

    ignored_parts = {".venv", "__pycache__", ".git"}
    for path in project_root.rglob("*.py"):
        if any(part in ignored_parts for part in path.parts):
            continue
        try:
            source = path.read_text(encoding="utf8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "TextBoxLayoutPolicy":
                definitions.append(
                    {"path": str(path.resolve()), "line": node.lineno}
                )
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "TextBoxLayoutPolicy":
                        imports.append(
                            {
                                "path": str(path.resolve()),
                                "line": node.lineno,
                                "module": node.module,
                            }
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.endswith("text_box_layout"):
                        imports.append(
                            {
                                "path": str(path.resolve()),
                                "line": node.lineno,
                                "module": alias.name,
                            }
                        )

    return {"definitions": definitions, "imports": imports}


def executed_setters(states: list[RuntimeState], slide_number: int) -> dict[str, bool]:
    events = {
        state.event
        for state in states
        if state.slide_number == slide_number
    }
    return {
        name: f"before_set_{name}" in events and f"after_set_{name}" in events
        for name in ("left", "top", "width", "height")
    }


def last_state(states: list[RuntimeState], slide_number: int) -> RuntimeState | None:
    relevant = [state for state in states if state.slide_number == slide_number]
    return relevant[-1] if relevant else None


def comparison(states: list[RuntimeState]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for slide_number, idx in ((2, 2), (6, 12), (8, 12)):
        setters = executed_setters(states, slide_number)
        final = last_state(states, slide_number)
        rows.append(
            {
                "slide_number": slide_number,
                "idx": idx,
                "controlled_height_only": {
                    "left_setter_reached": False,
                    "top_setter_reached": False,
                    "width_setter_reached": False,
                    "height_setter_reached": True,
                    "final_cx": 0,
                    "final_cy": "correct",
                },
                "controlled_full_sequence": {
                    "left_setter_reached": True,
                    "top_setter_reached": True,
                    "width_setter_reached": True,
                    "height_setter_reached": True,
                    "final_cx": "correct",
                    "final_cy": "correct",
                },
                "production": {
                    "left_setter_reached": setters["left"],
                    "top_setter_reached": setters["top"],
                    "width_setter_reached": setters["width"],
                    "height_setter_reached": setters["height"],
                    "final_cx": final.ext_cx if final else None,
                    "final_cy": final.ext_cy if final else None,
                },
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contract",
        default="data/input/it_skills_engine_validation_contract.json",
    )
    parser.add_argument(
        "--json-output",
        default="data/output/production_textbox_runtime_diagnostic.json",
    )
    parser.add_argument(
        "--markdown-output",
        default="data/output/production_textbox_runtime_diagnostic.md",
    )
    args = parser.parse_args()

    project_root = Path.cwd().resolve()
    module_path = Path(text_box_layout_module.__file__).resolve()
    method_source = inspect.getsource(TextBoxLayoutPolicy.apply)
    runtime = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "module_dunder_file": text_box_layout_module.__file__,
        "module_absolute_path": str(module_path),
        "module_mtime_utc": datetime.fromtimestamp(
            module_path.stat().st_mtime,
            tz=timezone.utc,
        ).isoformat(),
        "module_sha256": source_hash(module_path),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "apply_qualname": TextBoxLayoutPolicy.apply.__qualname__,
        "apply_module": TextBoxLayoutPolicy.apply.__module__,
        "apply_source_file": inspect.getsourcefile(TextBoxLayoutPolicy.apply),
        "apply_source_first_line": inspect.getsourcelines(TextBoxLayoutPolicy.apply)[1],
        "apply_source": method_source,
    }

    repository_scan = repository_matches(project_root)
    states: list[RuntimeState] = []
    original_apply = TextBoxLayoutPolicy.apply

    def traced_apply(
        self: TextBoxLayoutPolicy,
        shape: Any,
        *,
        archetype: str,
        placeholder_name: str,
        text: str,
        font_size_pt: float | None = None,
    ) -> Any:
        target = TARGETS.get((archetype, placeholder_name))
        if target is None:
            return original_apply(
                self,
                shape,
                archetype=archetype,
                placeholder_name=placeholder_name,
                text=text,
                font_size_pt=font_size_pt,
            )

        layout = matching_layout_placeholder(shape)
        states.append(
            make_state(
                shape=shape,
                slide_number=target["slide_number"],
                idx=target["idx"],
                archetype=archetype,
                placeholder_name=placeholder_name,
                event="apply_entry",
                reached=True,
            )
        )
        states.append(
            RuntimeState(
                slide_number=target["slide_number"],
                idx=target["idx"],
                archetype=archetype,
                placeholder_name=placeholder_name,
                event="layout_placeholder_entry",
                reached=layout is not None,
                assigned_value=None,
                assigned_type=None,
                left=integer(getattr(layout, "left", None)) if layout else None,
                top=integer(getattr(layout, "top", None)) if layout else None,
                width=integer(getattr(layout, "width", None)) if layout else None,
                height=integer(getattr(layout, "height", None)) if layout else None,
                width_inches=inch(getattr(layout, "width", None)) if layout else None,
                height_inches=inch(getattr(layout, "height", None)) if layout else None,
                xfrm_exists=shape_xfrm(layout) is not None if layout else False,
                off_x=child_attr(shape_xfrm(layout), "a:off", "x") if layout else None,
                off_y=child_attr(shape_xfrm(layout), "a:off", "y") if layout else None,
                ext_cx=child_attr(shape_xfrm(layout), "a:ext", "cx") if layout else None,
                ext_cy=child_attr(shape_xfrm(layout), "a:ext", "cy") if layout else None,
                xfrm_xml=xml(shape_xfrm(layout)) if layout else None,
                sppr_xml=xml(shape_sppr(layout)) if layout else None,
            )
        )

        proxy = TracedGeometryValue(
            shape,
            archetype=archetype,
            placeholder_name=placeholder_name,
            target=target,
            states=states,
        )
        result = original_apply(
            self,
            proxy,
            archetype=archetype,
            placeholder_name=placeholder_name,
            text=text,
            font_size_pt=font_size_pt,
        )
        states.append(
            make_state(
                shape=shape,
                slide_number=target["slide_number"],
                idx=target["idx"],
                archetype=archetype,
                placeholder_name=placeholder_name,
                event="immediately_before_apply_return_observed_by_wrapper",
                reached=True,
            )
        )
        return result

    TextBoxLayoutPolicy.apply = traced_apply
    try:
        build_result = DeckBuilder().build_from_contract_file(Path(args.contract))
    finally:
        TextBoxLayoutPolicy.apply = original_apply

    comparison_rows = comparison(states)
    payload = {
        "runtime": runtime,
        "repository_scan": repository_scan,
        "production_setter_trace": [asdict(state) for state in states],
        "comparison": comparison_rows,
        "build_result_repr": repr(build_result),
    }

    json_path = Path(args.json_output)
    md_path = Path(args.markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf8")

    lines = [
        "# Production TextBox Runtime Diagnostic",
        "",
        "## Runtime module identity",
        "",
        f"- Module: `{runtime['module_absolute_path']}`",
        f"- SHA-256: `{runtime['module_sha256']}`",
        f"- Modified UTC: `{runtime['module_mtime_utc']}`",
        f"- Python: `{runtime['python_executable']}`",
        f"- Version: `{runtime['python_version'].replace(chr(10), ' ')}`",
        "",
        "## Actual apply() source",
        "",
        "```python",
        method_source.rstrip(),
        "```",
        "",
        "## Production setter trace",
        "",
        "| Slide | idx | Event | Reached | Assigned | Width | Height | cx | cy |",
        "|---:|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for state in states:
        lines.append(
            f"| {state.slide_number} | {state.idx} | {state.event} | "
            f"{state.reached} | {state.assigned_value} | "
            f"{state.width_inches} | {state.height_inches} | "
            f"{state.ext_cx} | {state.ext_cy} |"
        )

    lines.extend(["", "## Controlled versus production", ""])
    for item in comparison_rows:
        lines.append(
            f"### Slide {item['slide_number']}, idx {item['idx']}"
        )
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(item, indent=2))
        lines.append("```")
        lines.append("")

    lines.extend(["## Repository definitions/imports", "", "```json"])
    lines.append(json.dumps(repository_scan, indent=2))
    lines.append("```")
    md_path.write_text("\n".join(lines), encoding="utf8")

    print(
        json.dumps(
            {
                "json_report": str(json_path),
                "markdown_report": str(md_path),
                "runtime_module": runtime["module_absolute_path"],
                "runtime_sha256": runtime["module_sha256"],
                "python_executable": runtime["python_executable"],
                "production_comparison": comparison_rows,
                "definitions_found": len(repository_scan["definitions"]),
                "imports_found": len(repository_scan["imports"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
