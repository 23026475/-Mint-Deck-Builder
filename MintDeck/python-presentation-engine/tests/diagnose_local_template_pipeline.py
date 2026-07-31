"""
Diagnostic runner for the local development template pipeline.

This script:
1. Finds the local FY27 AI-Ready .potx template.
2. Converts it to .pptx.
3. Loads the converted .pptx.
4. Enumerates slide layouts by name.
5. Writes a simple diagnostic report.

Run from the project root with:
    $env:PYTHONPATH = '.\\src'
    python .\\tests\\diagnose_local_template_pipeline.py
"""

from __future__ import annotations

import logging
from pathlib import Path

from presentation_engine.config import config
from presentation_engine.services.layout_mapper import LayoutMapper
from presentation_engine.services.potx_converter import PotxConverter
from presentation_engine.services.template_retrieval_service import TemplateRetrievalService


REPORT_FILE_NAME = "layout_diagnostic_report.txt"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    config.ensure_runtime_directories()

    retrieval_service = TemplateRetrievalService()
    potx_path = retrieval_service.retrieve_latest_template()

    converter = PotxConverter()
    pptx_path = converter.convert(
        potx_path=potx_path,
        pptx_path=config.template.converted_pptx_path,
        overwrite=True,
    )

    mapper = LayoutMapper()
    mapper.load(pptx_path)
    layout_names = mapper.available_layout_names()

    report_path = config.work_dir / REPORT_FILE_NAME
    write_report(report_path, potx_path, pptx_path, layout_names)

    print("Local template pipeline diagnostic succeeded.")
    print(f"POTX template: {potx_path}")
    print(f"Converted PPTX: {pptx_path}")
    print(f"Layout count: {len(layout_names)}")
    print(f"Diagnostic report: {report_path}")
    print("Discovered layouts:")
    for layout_name in layout_names:
        print(f"- {layout_name}")


def write_report(
    report_path: Path,
    potx_path: Path,
    pptx_path: Path,
    layout_names: tuple[str, ...],
) -> None:
    """Write a plain-text diagnostic report for discovered layouts."""

    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "Presentation Engine Layout Diagnostic Report",
        "============================================",
        "",
        f"POTX template: {potx_path}",
        f"Converted PPTX: {pptx_path}",
        f"Layout count: {len(layout_names)}",
        "",
        "Discovered layouts:",
    ]

    lines.extend(f"- {layout_name}" for layout_name in layout_names)
    report_path.write_text("\n".join(lines), encoding="utf8")


if __name__ == "__main__":
    main()
