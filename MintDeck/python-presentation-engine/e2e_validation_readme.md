# Exact-match E2E Validation Package

This package contains:

1. `exact_match_e2e_contract.json` - JSON contract that exercises every currently supported exact-match archetype at least once.
2. `run_exact_match_e2e_validation.py` - local validation runner for the project root.

I could not generate the PPTX inside this chat environment because the local engine runtime and binary FY27 `.potx` template are not available as executable local project files here. Run the validation script from your project root to generate the actual PPTX and validation report.

Expected local outputs after running the script:

- `data/output/Contoso Manufacturing - AI-Ready Exact-Match Archetype Validation - <date>.pptx`
- `data/output/exact_match_e2e_validation_report.json`

The script validates:

- slide count
- archetype-to-layout resolution
- actual slide layout name
- duplicate ZIP entries
- unresolved placeholder/prompt text
- per-slide PASS/FAIL status
