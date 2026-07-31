"""
Small runtime test for TemplateRetrievalService.

This test downloads the configured FY27 AI-Ready .potx template, confirms the
file exists, prints the filename and full local path, and reports success.
It does not open, convert, or modify the template.

Before running, set:
PowerShell:
    $env:PRESENTATION_ENGINE_SHAREPOINT_TEMPLATE_URL = "https://your-sharepoint-download-url/FY27%20AI-Ready%20v3.0.potx"

Then run from the project root:
    python tests/test_template_retrieval_service.py
"""

from __future__ import annotations

import logging

from presentation_engine.services.template_retrieval_service import TemplateRetrievalService


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    service = TemplateRetrievalService()
    template_path = service.retrieve_latest_template()

    print("Template download test succeeded.")
    print(f"Template filename: {template_path.name}")
    print(f"Full local path: {template_path}")


if __name__ == "__main__":
    main()
