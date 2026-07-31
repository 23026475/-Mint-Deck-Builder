"""
Central configuration for the Python Presentation Engine.

This module keeps runtime paths in one place and reads environment variables
where deployment-specific values are expected. It intentionally avoids any
PowerPoint generation logic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).resolve().parents[2]


def _env(name: str, default: Optional[str] = None) -> Optional:
    """Return an environment variable value, or a default when not set."""
    return os.getenv(name, default)


def _path_from_env(name: str, default: Path) -> Path:
    """Return a Path from an environment variable, falling back to a default."""
    value = _env(name)
    return Path(value).expanduser().resolve() if value else default.resolve()


@dataclass(frozen=True)
class SharePointConfig:
    """SharePoint source configuration for the published PowerPoint template."""

    template_url: Optional[str]
    template_file_name: str


@dataclass(frozen=True)
class TemplateConfig:
    """Template paths used during download, conversion, and development."""

    download_dir: Path
    downloaded_potx_path: Path
    converted_pptx_path: Path

    development_mode: bool
    local_template_root: Path


@dataclass(frozen=True)
class InputConfig:
    """Input JSON contract paths produced by the Copilot Studio agent."""

    input_dir: Path
    contract_path: Path


@dataclass(frozen=True)
class OutputConfig:
    """Output paths for generated PowerPoint presentations."""

    output_dir: Path


@dataclass(frozen=True)
class ValidationConfig:
    """Template validation configuration."""

    archetype_baseline_path: Path
    report_output_dir: Path


@dataclass(frozen=True)
class LoggingConfig:
    """Logging configuration for engine diagnostics."""

    log_dir: Path
    log_file_path: Path
    log_level: str


@dataclass(frozen=True)
class EngineConfig:
    """Top-level configuration object for the Presentation Engine."""

    base_dir: Path
    work_dir: Path
    sharepoint: SharePointConfig
    template: TemplateConfig
    input: InputConfig
    output: OutputConfig
    validation: ValidationConfig
    logging: LoggingConfig

    @classmethod
    def from_environment(cls) -> "EngineConfig":
        """Build configuration from environment variables and safe defaults."""

        base_dir = _path_from_env(
            "PRESENTATION_ENGINE_BASE_DIR",
            BASE_DIR,
        )

        work_dir = _path_from_env(
            "PRESENTATION_ENGINE_WORK_DIR",
            base_dir / "data" / "work",
        )

        input_dir = _path_from_env(
            "PRESENTATION_ENGINE_INPUT_DIR",
            base_dir / "data" / "input",
        )

        output_dir = _path_from_env(
            "PRESENTATION_ENGINE_OUTPUT_DIR",
            base_dir / "data" / "output",
        )

        log_dir = _path_from_env(
            "PRESENTATION_ENGINE_LOG_DIR",
            base_dir / "logs",
        )

        template_file_name = _env(
            "PRESENTATION_ENGINE_TEMPLATE_FILE_NAME",
            "FY27 AI-Ready.potx",
        )

        converted_template_file_name = _env(
            "PRESENTATION_ENGINE_CONVERTED_TEMPLATE_FILE_NAME",
            "FY27 AI-Ready.work.pptx",
        )

        contract_file_name = _env(
            "PRESENTATION_ENGINE_CONTRACT_FILE_NAME",
            "deck-contract.json",
        )

        archetype_baseline_file_name = _env(
            "PRESENTATION_ENGINE_ARCHETYPE_BASELINE_FILE_NAME",
            "archetype-baseline.json",
        )

        log_file_name = _env(
            "PRESENTATION_ENGINE_LOG_FILE_NAME",
            "presentation-engine.log",
        )

        development_mode = (
            _env(
                "PRESENTATION_ENGINE_DEVELOPMENT_MODE",
                "false",
            ).lower()
            == "true"
        )

        local_template_root = _path_from_env(
            "PRESENTATION_ENGINE_LOCAL_TEMPLATE_ROOT",
            base_dir,
        )

        return cls(
            base_dir=base_dir,
            work_dir=work_dir,
            sharepoint=SharePointConfig(
                template_url=_env(
                    "PRESENTATION_ENGINE_SHAREPOINT_TEMPLATE_URL"
                ),
                template_file_name=template_file_name,
            ),
            template=TemplateConfig(
                download_dir=work_dir / "template",
                downloaded_potx_path=(
                    work_dir / "template" / template_file_name
                ),
                converted_pptx_path=(
                    work_dir
                    / "template"
                    / converted_template_file_name
                ),
                development_mode=development_mode,
                local_template_root=local_template_root,
            ),
            input=InputConfig(
                input_dir=input_dir,
                contract_path=input_dir / contract_file_name,
            ),
            output=OutputConfig(
                output_dir=output_dir,
            ),
            validation=ValidationConfig(
                archetype_baseline_path=(
                    input_dir / archetype_baseline_file_name
                ),
                report_output_dir=(
                    output_dir / "validation"
                ),
            ),
            logging=LoggingConfig(
                log_dir=log_dir,
                log_file_path=log_dir / log_file_name,
                log_level=_env(
                    "PRESENTATION_ENGINE_LOG_LEVEL",
                    "INFO",
                ),
            ),
        )

    def ensure_runtime_directories(self) -> None:
        """Create runtime directories required by the engine."""

        directories = [
            self.work_dir,
            self.template.download_dir,
            self.input.input_dir,
            self.output.output_dir,
            self.validation.report_output_dir,
            self.logging.log_dir,
        ]

        for directory in directories:
            directory.mkdir(
                parents=True,
                exist_ok=True,
            )


config = EngineConfig.from_environment()