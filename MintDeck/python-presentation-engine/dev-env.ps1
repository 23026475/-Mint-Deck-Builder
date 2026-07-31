$env:PYTHONPATH = ".\src"
$env:PRESENTATION_ENGINE_TEMPLATE_FILE_NAME = "FY27 AI-Ready v3.0.potx"
$env:PRESENTATION_ENGINE_CONVERTED_TEMPLATE_FILE_NAME = "FY27 AI-Ready v3.0.work.pptx"

Write-Host "Development environment loaded."
Write-Host "PYTHONPATH = $env:PYTHONPATH"
Write-Host "Template = $env:PRESENTATION_ENGINE_TEMPLATE_FILE_NAME"
Write-Host "Converted template = $env:PRESENTATION_ENGINE_CONVERTED_TEMPLATE_FILE_NAME"