# Engine Starter Kit — AI Presentation Builder
For: Ndivhuwo (IT) · From: Carel · 29 Jul 2026

Everything here was built and battle-tested during the FY27 template programme. It encodes the
knowledge your generation engine needs, so you start from proven ground.

## Contents
1. **Mint Deck Standard - Layout & Placeholder Maps.md** — the full standard: every layout in
   FY27 AI-Ready v3.0.potx by NAME with its placeholder idx map (which idx takes the kicker,
   title, cards, callouts...), the type ramp, colour/accessibility rules, density rules, story
   structure, and the list of retired layouts your engine must never reference.
2. **kit.py** — python-pptx utilities for bespoke shapes (cards, stat blocks, callouts, covers)
   already colour-correct for the Mint palette.
3. **archetype-baseline.json** — the 30 slide archetypes with required elements; use it to map
   outline sections to layouts.
4. **classify_deck.py** — rule-based classifier that maps existing slides to archetypes; useful
   for validation and for rebuild pipelines.

## Engine ground rules
- Input: structured outline from the Copilot Studio agent (one object per slide: archetype,
  action title, content fields). Output: .pptx built on FY27 AI-Ready v3.0.potx.
- ALWAYS load the template from the published SharePoint copy at runtime — never bundle a snapshot.
- Find layouts BY NAME, never by index (part numbers change between versions).
- Fill every placeholder or delete it — never leave prompt text visible.
- Template-level styling lives in each layout's lstStyle; do not add run-level colour/size
  overrides in generated slides.
- QA gate: render output to images and check text fits, contrast, and that no placeholder
  prompts leaked, before returning the file to the user.

## Workflow to copy (proven in the programme)
potx → flip content type to pptx → python-pptx → delete the 24 sample slides → add slides from
outline via layout name + placeholder idx → save. Slide deletion: drop the relationship AND the
sldIdLst entry together.
