# Phase 2 — Markdown as an Input Format (spec)
Status: backlog, start AFTER the first milestone (3-slide deck end to end) is signed off.

## Why
Marp (marp.app) proves people like authoring decks as Markdown: fast, plain text, git-friendly.
We adopt the AUTHORING experience but not Marp's renderer — Marp's PPTX output is baked images
with no layouts or placeholders, which bypasses the template, the Brand Kit and the Brand
Reviewer. Instead: Markdown in → our outline JSON → the engine renders native FY27 v3.0 pptx.
One extra parser, zero new output systems.

## Authoring convention (what users write)
```markdown
---
client: Acme Bank
title: Managed Security Proposal
mode: READ
---

# cover: Managed Security Proposal
kicker: PREPARED FOR ACME BANK
subtitle: A safer estate in 12 months

# cards3: Three risks are compounding every quarter
kicker: THE SITUATION
- Visibility :: 31% of sensitive data is unlabelled.
- Identity :: Standing admin access remains in place.
- Audit :: Evidence is rebuilt by hand every cycle.

# closing: From today to kickoff
- Confirm the decision and owners
- Sign the engagement documents
- Schedule kickoff within two weeks
```

## Parsing rules
1. YAML front matter → deck metadata (client, title, mode READ/STAGE).
2. Every `# ` heading starts a slide: `# <archetype>: <action title>`. The archetype must exist
   in archetype-baseline.json; the action title max 15 words (reject otherwise, with a helpful
   message telling the author to shorten it).
3. `key: value` lines under a heading → named fields (kicker, subtitle, intro, callout...).
4. Bullets map to the archetype's list zones. For card-type archetypes, `Title :: body` splits
   a bullet into card title and card body.
5. Anything that does not parse → clear error naming the line, never a silent guess.
6. Parser output = exactly the outline JSON already defined in the BUILD GUIDE (Step 3), so the
   engine does not change at all.

## Validation (same gates as any input)
Density rules (≤60 words/slide body), title length, archetype exists, required fields present.
Reject early with friendly errors — the author fixes the text, the engine never "makes do".

## Nice-to-haves (later)
- VS Code snippet file for the convention.
- A `--watch` mode: save the .md, get a fresh rendered preview PDF.
