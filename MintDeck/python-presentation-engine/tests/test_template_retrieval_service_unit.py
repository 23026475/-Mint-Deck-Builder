"""
Unit-style test for TemplateRetrievalService using dependency injection.

This verifies the service behavior without calling SharePoint and without
opening or modifying the template.
"""

from __future__ import annotations

import sys
import tempfile
import types
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace


# The production service imports presentation_engine.config. In this standalone
# unit test, we stub that module before importing the service so the test can run
# outside the full project package structure.
fake_presentation_engine = types.ModuleType("presentation_engine")
fake_config_module = types.ModuleType("presentation_engine.config")
fake_config_module.EngineConfig = object
fake_config_module.config = SimpleNamespace(
    sharepoint=SimpleNamespace(template_url="https://sharepoint.example.com/FY27%20AI-Ready%20v3.0.potx"),
    template=SimpleNamespace(downloaded_potx_path=Path("data/work/FY27 AI-Ready v3.0.potx")),
)
sys.modules.setdefault("presentation_engine", fake_presentation_engine)
sys.modules.setdefault("presentation_engine.config", fake_config_module)

from presentation_engine.services.template_retrieval_service import (
    TemplateRetrievalService,
)


@dataclass(frozen=True)
class FakeDownloadClient:
    content: bytes = b"fake potx package bytes"

    def download(self, source_url: str, destination_path: Path) -> Path:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(self.content)
        return destination_path


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        work_dir = Path(temp_dir) / "data" / "work"
        destination_path = work_dir / "FY27 AI-Ready v3.0.potx"

        fake_config = SimpleNamespace(
            sharepoint=SimpleNamespace(
                template_url="https://sharepoint.example.com/FY27%20AI-Ready%20v3.0.potx"
            ),
            template=SimpleNamespace(downloaded_potx_path=destination_path),
        )

        service = TemplateRetrievalService(
            engine_config=fake_config,
            download_client=FakeDownloadClient(),
        )

        template_path = service.retrieve_latest_template()

        assert template_path.exists(), "Expected downloaded template to exist."
        assert template_path.suffix.lower() == ".potx", "Expected .potx extension."

        print("Template retrieval unit test succeeded.")
        print(f"Template filename: {template_path.name}")
        print(f"Full local path: {template_path}")


if __name__ == "__main__":
    main()
