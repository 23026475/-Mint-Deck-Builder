$ProjectName = "python-presentation-engine"

# Root project folder
New-Item -ItemType Directory -Path $ProjectName -Force | Out-Null

# Main source folders
New-Item -ItemType Directory -Path "$ProjectName\src" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\src\presentation_engine" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\src\presentation_engine\contracts" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\src\presentation_engine\core" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\src\presentation_engine\services" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\src\presentation_engine\adapters" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\src\presentation_engine\builders" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\src\presentation_engine\validators" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\src\presentation_engine\qa" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\src\presentation_engine\exceptions" -Force | Out-Null

# Configuration and data folders
New-Item -ItemType Directory -Path "$ProjectName\config" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\data" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\data\input" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\data\output" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\data\work" -Force | Out-Null

# Documentation and tests
New-Item -ItemType Directory -Path "$ProjectName\docs" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\tests" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\tests\unit" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\tests\integration" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectName\tests\fixtures" -Force | Out-Null

# Root files
New-Item -ItemType File -Path "$ProjectName\README.md" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\requirements.txt" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\pyproject.toml" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\.gitignore" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\.env.example" -Force | Out-Null

# Application entry point
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\__init__.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\main.py" -Force | Out-Null

# Contracts
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\contracts\__init__.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\contracts\deck_contract.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\contracts\slide_contract.py" -Force | Out-Null

# Core interfaces and orchestration
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\core\__init__.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\core\interfaces.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\core\engine.py" -Force | Out-Null

# Services
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\services\__init__.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\services\template_service.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\services\contract_service.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\services\layout_service.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\services\output_service.py" -Force | Out-Null

# Adapters
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\adapters\__init__.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\adapters\pptx_adapter.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\adapters\sharepoint_adapter.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\adapters\file_system_adapter.py" -Force | Out-Null

# Builders
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\builders\__init__.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\builders\deck_builder.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\builders\slide_builder.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\builders\placeholder_builder.py" -Force | Out-Null

# Validators
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\validators\__init__.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\validators\contract_validator.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\validators\density_validator.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\validators\archetype_validator.py" -Force | Out-Null

# QA
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\qa\__init__.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\qa\qa_runner.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\qa\slide_renderer.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\qa\prompt_leak_checker.py" -Force | Out-Null

# Exceptions
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\exceptions\__init__.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\src\presentation_engine\exceptions\engine_exceptions.py" -Force | Out-Null

# Config files
New-Item -ItemType File -Path "$ProjectName\config\settings.example.json" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\config\archetype-baseline.json" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\config\layout-placeholder-map.json" -Force | Out-Null

# Documentation files
New-Item -ItemType File -Path "$ProjectName\docs\architecture.md" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\docs\json-contract.md" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\docs\solid-principles.md" -Force | Out-Null

# Test files
New-Item -ItemType File -Path "$ProjectName\tests\__init__.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\tests\unit\__init__.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\tests\integration\__init__.py" -Force | Out-Null
New-Item -ItemType File -Path "$ProjectName\tests\fixtures\sample_deck_contract.json" -Force | Out-Null

Write-Host "Project structure created successfully: $ProjectName"