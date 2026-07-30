# Presentation Engine — Step-by-Step Build Guide
For Ndivhuwo · 29 Jul 2026 · Read this top to bottom before writing code. Every snippet below is
tested and comes from the pipeline used to build the template itself.

## Step 0 — Set up your environment
1. Install Python 3.10 or newer.
2. `pip install python-pptx pillow`
3. Install LibreOffice (free) — we use it headless to render slides to images for QA.
4. Confirm: `python -c "import pptx; print(pptx.__version__)"`

## Step 1 — Get the template (the right way)
Always download **FY27 AI-Ready v3.0.potx** from the published SharePoint copy AT RUNTIME.
Never commit a copy of the template into your repo — the day marketing ships v3.1 your engine
must pick it up automatically.

python-pptx cannot open a .potx directly. Flip the content type first:

```python
import shutil, zipfile, os

def potx_to_pptx(potx_path, pptx_path):
    tmp = pptx_path + "_x"
    with zipfile.ZipFile(potx_path) as z:
        z.extractall(tmp)
    ct_file = os.path.join(tmp, "[Content_Types].xml")
    ct = open(ct_file, encoding="utf8").read()
    ct = ct.replace("presentationml.template.main+xml",
                    "presentationml.presentation.main+xml")
    open(ct_file, "w", encoding="utf8").write(ct)
    if os.path.exists(pptx_path): os.remove(pptx_path)
    shutil.make_archive(pptx_path, "zip", tmp)
    os.rename(pptx_path + ".zip", pptx_path)
    shutil.rmtree(tmp)
```

## Step 2 — Learn the template from code
Run this once and keep the output next to you. It prints every layout with its placeholders:

```python
from pptx import Presentation
prs = Presentation("work.pptx")
for lay in prs.slide_masters[0].slide_layouts:
    print("LAYOUT:", lay.name)
    for ph in lay.placeholders:
        print("   idx", ph.placeholder_format.idx,
              "type", ph.placeholder_format.type, "name", ph.name)
```

Cross-check what you see against **Mint Deck Standard - Layout & Placeholder Maps.md**.
RULES: find layouts **by name**, never by position (numbering changes between versions), and
never use a layout listed as retired in that document.

## Step 3 — Define the input contract (agree with Carel before coding)
Your Copilot Studio agent produces the outline. Structure it as JSON — one object per slide:

```json
{
  "deck": {"client": "Acme Bank", "title": "Managed Security Proposal", "mode": "READ"},
  "slides": [
    {"archetype": "cover", "fields": {"title": "Managed Security Proposal",
      "kicker": "PREPARED FOR ACME BANK", "subtitle": "A safer estate in 12 months"}},
    {"archetype": "cards3", "action_title": "Three risks are compounding every quarter",
      "fields": {"kicker": "THE SITUATION",
        "cards": [{"title": "Visibility", "body": "31% of data is unlabelled."},
                   {"title": "Identity", "body": "Standing admin access remains."},
                   {"title": "Audit", "body": "Evidence is rebuilt by hand."}]}},
    {"archetype": "closing", "action_title": "From today to kickoff",
      "fields": {"steps": ["Confirm owners", "Sign", "Kick off in two weeks"]}}
  ]
}
```

`archetype` maps to a layout via **archetype-baseline.json** — it lists all 30 slide types and
what each requires. Titles must be ACTION TITLES (a full-sentence takeaway, max 15 words),
which the agent already produces.

## Step 4 — Start every run by deleting the sample slides
The template ships with 24 sample slides (Copilot learns from them — your engine must not
keep them). Delete them like this and ONLY like this, or the file corrupts:

```python
def delete_all_slides(prs):
    xml_slides = prs.slides._sldIdLst
    for sld in list(xml_slides):
        rId = sld.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        prs.part.drop_rel(rId)      # BOTH lines are required, in this order
        xml_slides.remove(sld)
```

## Step 5 — Add slides and fill placeholders
```python
def layout_by_name(prs, name):
    for lay in prs.slide_masters[0].slide_layouts:
        if lay.name == name:
            return lay
    raise ValueError(f"Layout not found: {name}")

lay = layout_by_name(prs, "Content – Cards 3")   # note: – is an en-dash, copy from the map doc
slide = prs.slides.add_slide(lay)
for ph in slide.placeholders:
    idx = ph.placeholder_format.idx
    if idx == 11: ph.text = data["fields"]["kicker"]
    elif idx == 0: ph.text = data["action_title"]
    # ... map every idx per the Layout & Placeholder Maps document
```

**Fill or delete — never leave a placeholder untouched**, or its prompt text ("Click to edit…")
can show in exports:

```python
def drop_empty_placeholders(slide, filled_idx):
    for ph in list(slide.placeholders):
        if ph.placeholder_format.idx not in filled_idx and ph.has_text_frame:
            ph._element.getparent().remove(ph._element)
```

## Step 6 — Never style in code
Do not set `.font.size`, `.font.color`, `.font.name` or alignment anywhere. All styling lives in
the template's layouts; plain `ph.text = "..."` inherits it. If output looks wrong, the fix goes
into the template (talk to Carel), never into engine code. The single exception: `kit.py` helpers
for bespoke shapes are pre-approved and already brand-correct.

## Step 7 — Respect the density rules
Before building a slide, validate the content against the rules in the map document:
max ~60 words per slide body (hard ceiling 90), 3–5 points per card zone, titles ≤ 15 words.
If content exceeds the limits, reject the outline entry back to the agent rather than shrinking
text — shrinking is how decks go off-brand.

## Step 8 — QA gate (mandatory, before returning any file)
```bash
soffice --headless --convert-to pdf output.pptx
pdftoppm -jpeg -r 50 output.pdf page
```
Then check programmatically and/or visually:
1. No slide contains "Click to edit" or "Click icon" (prompt leak).
2. Slide count equals outline count.
3. Spot-check images: titles not wrapping beyond 2 lines, nothing overlapping.
A deck that fails QA is not delivered — fix and re-run.

## Step 9 — Save and name
`{Client} - {Deck title} - {yyyy-mm-dd}.pptx`, saved as .pptx (not .potx). The generated file
must never be saved back over the template.

## Step 10 — First milestone
One deck end to end from a 3-slide outline (cover, cards3, closing). Compare your output
side by side with the same slides in "Mint Showcase v3.0 (Review Copy).pptx" — they should be
visually identical apart from the words. Send both to Carel for sign-off, then extend to all 30
archetypes using archetype-baseline.json as your checklist.

## Known pitfalls (each of these cost us a day — avoid them)
- Deleting slides by removing only the sldIdLst entry → corrupt file. Use the Step 4 code.
- Referencing layouts by index → breaks whenever the template is re-saved. Names only.
- Setting run-level colours/sizes → slides stop inheriting template updates.
- Bundling a template snapshot → engine drifts from the published standard.
- Long titles at display sizes → validate title length BEFORE building, not after.
- The en-dash: layout names use "–" not "-". Copy names from the map document exactly.

Questions: ask Carel early and often. Rather ask than guess.
