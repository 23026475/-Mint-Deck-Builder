---
name: mint-deck-style
description: Build Mint Group presentations in the FY27 brand design language. Use whenever creating, rebuilding, or restyling a PowerPoint deck for Mint Group or its clients — sales proposals, RFQ responses, assessments, internal decks. Ensures output uses the FY27 AI-Ready template layouts and placeholders, Mint colours and Lato typography, and WCAG AA-accessible styling.
---

# Mint Group Deck Style

Build every Mint deck FROM the template, not from scratch:
`Mint > Marketing > PowertPoint Template > FY27 AI-Ready v3.0.potx` (or latest version in that folder).

## Workflow

1. Copy the .potx, change the content-type override for `/ppt/presentation.xml` from
   `presentationml.template.main+xml` to `presentationml.presentation.main+xml`, open with python-pptx.
2. Delete the 24 sample slides (they are style exemplars, not content).
3. For each content slide, pick a layout from the map below and fill its placeholders by idx.
4. Only when no layout fits (score bars, timelines, bespoke diagrams) draw shapes with `kit.py`
   on the Blank layout, using ONLY the palette below.
5. QA: render to images, check text fits, block order matches badge numbers, contrast.

## Layout map (name → placeholder idx)

| Layout | Placeholders (idx) |
|---|---|
| Cover – Brand | kicker 11, title 0, subtitle 2, abstract 3, prepared-by 4 |
| Cover – Dark / Closing – Next Steps | kicker 11, title 0, subtitle 2 (cover), abstract 3, footer-line 4 / steps 12, footer-line 13 |
| Agenda – 6 Items / – 5 Items | title 0, item heading+text pairs 10/11 … 20/21 (order follows numbered badges) |
| Content – Cards 3 / Cards 4 | kicker 11, title 0, intro 12 (optional), card title/body 20/21, 22/23, 24/25(, 26/27), callout 40 |
| Content – Process Flow | same as cards; steps 20/21…26/27, note 40 |
| Content – Table | kicker 11, title 0, intro 12, TABLE ph 10 (insert_table), callout 40 |
| Content – Pricing Stat | kicker 11, title 0, lead-in 13, bullet cols 14/15, stat card: kicker 20, number 21, secondary 22, term 23, note 24, fine print 41 |
| Content – Image Right | kicker 11, title 0, body 12, PICTURE ph 20 |
| Content Slide 1 – Body + CTA | title 0, subheading 2, body 3, CTA 4 |
| Title and Content 1–7 | title 0, body 10 (bulleted) |
| Meet the Team | title 0, name/role pairs 10–15, PICTURE phs 20–22 |
| Blue/White Section Divider | title 0 |
| Content Slide 5 – 3 Blocks | title 0, sub 2, body 3; blocks LEFT=12/13, MIDDLE=10/11, RIGHT=14/15 |

Delete optional placeholders you don't fill (intro 12, callout 40) so prompts don't render.
Footer ph idx 3 on content layouts: fill with `Mint Group · Client · Deck · Year`.

## Palette (accessibility-adjusted usage)

| Use | Hex |
|---|---|
| Navy (backgrounds, table headers, card titles) | 243C7A |
| Blue (kickers on white, card titles) | 184B9A |
| Green (card titles, positive status) | 439E46 |
| Light green (accents ON DARK only — fails on white) | 89C146 |
| Orange (card bars; titles only at ≥14pt bold) | F15927 |
| Dark orange (small orange TEXT: callout lead-ins, status words) | B5450F |
| Ice blue (small text on navy) | BDD3F0 |
| Light blue (large accents; NEVER small text on white) | 65A1D7 |
| Body grey | 475054 · footer grey 6C777D |
| Tints: light blue E9F3F7 · peach FDEEE4 |

Card colour cycle left→right: 184B9A, 439E46, F15927, 243C7A.

## Typography — Lato throughout

Cover title 38–40pt · content titles 23–30pt · kickers 10.5–12pt bold UPPERCASE ·
card titles 14pt bold · body 10–11pt · footers 8.5–10pt. Keep titles ≤2 lines (no auto-shrink in Copilot).

## Hard rules

- Never replace a placeholder with a text box; never rename layouts.
- Status/meaning words always as text, colour is reinforcement only.
- Alt text on every inserted image; decorative art marked decorative.
- Numbers/stats get the Pricing Stat card or big-number treatment, not a bullet.
- Icons and extra brand elements: copy from `Mint Brand Assets.pptx` in the same folder. Canonical image/icon library (SharePoint): https://mintmanagement.sharepoint.com/sites/Marketing/Mint_CI_Elements (Group Marketing > Mint CI Elements; filter Document Type = Imagery/Iconography). Use these assets for photos and icons in Mint decks; never stock images from elsewhere. Access paths: (1) if a OneDrive-synced local copy of the library is available in the connected folders, use it directly; (2) via Claude-in-Chrome with Carel's authenticated session; (3) the fallback is Mint Brand Assets.pptx in the template folder.
- Tables: navy 243C7A header row, white bold 11pt header text, 10–10.5pt grey body, zebra banding.

## kit.py (bundled)

For bespoke slides only: `card_row, flow_row, statcard, callout2, cover, closing, header, footer,
bullets_col` plus score-bar/timeline patterns — see function signatures in kit.py. All colours already brand-correct.

## Transitions & motion

Default standard: **Fade, fast (~0.35s), applied uniformly to every slide** — inject
`<p:transition spd="fast"><p:fade/></p:transition>` after `clrMapOvr` in each slide XML.

When to deviate:
- **Read/leave-behind decks** (proposals, RFQ responses, anything sent as a file or PDF): transitions are
  irrelevant or lost in PDF — Fade default or none; NEVER rely on motion to convey meaning.
- **Presented decks** (pitches, townhalls): keep the uniform Fade; optionally use **Morph** on a deliberate
  before/after or step-progression pair where objects visibly move — max 2–3 Morph moments per deck.
- **Never**: mixed transition styles per slide, Push/Zoom/Vortex-class effects, sounds, auto-advance
  (except unattended kiosk loops), or entrance animations on body text (accessibility: vestibular motion
  sensitivity, and screen readers announce content before it appears). Flashing content is prohibited (WCAG 2.3.1).
- Object animation: only Appear/Fade for staged reveals when the presenter explicitly asks; one animation
  scheme per deck.

## Type ramp — consistency across the deck while using each slide's estate

One fixed ramp, used on EVERY slide. Fit content to the ramp by sizing CONTAINERS and cutting
words — never by shrinking text below the ramp.

| Role | Size |
|---|---|
| Cover title | 38–40pt |
| Content slide title | 23–30pt (pick one per deck and keep it) |
| Kicker | 11pt bold UPPERCASE |
| Big stat / price | 26pt bold (one line preferred; container allows two) |
| Card/step titles | 14pt bold |
| Body & bullets | 10.5–11pt |
| Secondary stat / lead-ins | 12–14pt |
| Captions, fine print, footers | 9.5–10pt — the floor. Nothing smaller, ever. |

Estate rules: if a slide is sparse, enlarge the container/whitespace or promote content to a bigger
archetype (bullets → cards; one number → Pricing Stat card) — don't inflate font sizes ad hoc.
If content overflows at ramp size: cut words, split the slide, or switch to a denser archetype (cards →
table). Contrast rule for dark cards on light slides: small text on the card uses ice blue BDD3F0 /
white — never the dark-blue-on-white colours.

## v1.5 layout additions (archetype baseline v1.1)

| Layout | Placeholders (idx) |
|---|---|
| Content – Comparison | kicker 11, title 0, column headings 20/22, column points 21/23, verdict 40 |
| Statement – Full Bleed | full-bleed PICTURE ph 20, kicker 11, statement (title), support 2 — text phs carry their own semi-transparent navy bands; never remove their fills |
| KPI – 4 Stats | kicker 11, title 0, number/label pairs 20/21…26/27, context 40 |
| Roadmap – 4 Phases | kicker 11, title 0, phase-band/milestones pairs 20/21…26/27 (bands: blue/navy/orange/green, 14pt), note 40 |
| Content – Chart | kicker 11, title 0, CHART ph 10 (insert_chart), takeaway 13/14, source 41 |

Callout placeholders (idx 40) on cards/table/comparison layouts now carry their own tinted band —
delete the placeholder and the band goes with it. Table body text: 2A3338, not 475054.

## v1.6 additions (baseline v1.2 — corpus-validated)

| Layout | Placeholders (idx) |
|---|---|
| Logo Wall | kicker 11, title 0, PICTURE phs 20–27 (8 tiles), caption 40 |
| Quote | quotation 20, name 21, role 22, headshot PICTURE ph 30 |

Corpus-mined rules: ≤60 words/slide target (hard ceiling 90); legacy-colour mapping when rebuilding
old decks (1BB0CE→65A1D7/184B9A · F36F21→F15927 · FFC000→89C146 · dark greys→475054/2A3338);
flag decks >35 slides for splitting.

## Density & whitespace rules (v1.7)

- Content groups sit CENTRED in the content zone (1.6"–6.4") — never top-hugging with a dead bottom third.
- Callout/note bands sit 0.25–0.4" below the content group, not pinned to the page bottom.
- Fill the container: 3–5 points or 25–45 words per card zone. If content is thinner, switch to a
  bigger-type archetype (KPI tiles, Statement) instead of leaving hollow cards.
- Card body 11pt; comparison points 11.5pt; whitespace balanced above/below the group reads
  intentional — all slack at the bottom reads broken.

## CI frame (v1.8)

All light content layouts carry the Mint CI frame: blue gradient border, white rounded content card,
mint logo bottom-right (baked into layout background — never add your own logo or border).
Safe zone inside the card: x 0.6"–12.9", y 0.55"–6.35". Header block starts x=0.62"; footers sit at
y=6.24" inside the card. Dark layouts (covers, dividers, statement, closing) remain full-bleed.

## v1.9 additions — baseline complete (30/30 archetypes)

| Layout | Placeholders (idx) |
|---|---|
| Thesis | kicker 11, title 0, claims 20/21, pivot question 22, verdict (navy box) 23, footnote 24 |
| Case Study | kicker 11, title 0, client line 13, challenge 20, approach 21, outcome 22, headline result 40 |
| FAQ | kicker 11, title 0, Q/A pairs 20/21 · 22/23 · 24/25 · 26/27 |
| Org Chart | kicker 11, title 0, top role 20, leads 21/22/23, teams 24/25/26, note 40 |
| Matrix 2x2 | kicker 11, title 0, quadrant title/items 20/21…26/27, axis labels 30 (vertical) / 31 (horizontal) |

Use Thesis as slide 2–3 of persuasion decks: two claims → pivot question → verdict the deck must prove.

## Type ramp v2.0 (supersedes earlier ramp)

Kickers 12pt · content titles 26pt · intro 13pt · card/step/quadrant titles 16pt · body & bullets 13pt ·
comparison points 13.5pt · KPI numbers 34pt / labels 13pt · table body 12pt, header 12.5pt bold ·
callouts 12.5pt · thesis question 22pt / verdict 16pt · quote 26pt · statement 36pt · footers 9.5pt floor.

## Storytelling standard (benchmark cross-check, July 2026)

**Action titles — mandatory.** Every content-slide title is a full-sentence takeaway (≤58 chars ideal,
≤15 words hard): "Governance catches adoption by month 9" — never "The trajectory". Exempt: Agenda,
dividers, Thank You. **Titles-only test:** before delivery, read only the titles in order — they must
form the complete argument. If they don't, fix titles before touching slides.
**Vertical logic:** every title claim is proven by that slide's own content. One governing message per slide.

**Story spine (Raskin × SCQA, mapped to archetypes):**
1. Shift in the world → Statement – Full Bleed (never open with "about us")
2. Winners & losers / stakes → Cards 3 or KPI – 4 Stats
3. Answer up front → Thesis (SCQA's A comes early)
4. Promised land → Chart/KPI showing the future state as CLIENT outcome, not product
5. Magic gifts → Cards 4 / Process Flow / Roadmap (product only AFTER the promised land)
6. Proof → Case Study + Quote + Logo Wall
7. Ask → Summary + CTA, Closing – Next Steps
Include ONE deliberate S.T.A.R. moment per deck (a shocking stat on KPI, or a Statement slide).
Draft the storyline as a titles-only outline FIRST (dot-dash), test horizontal logic, then build slides.

**Two modes — choose before building, never mix:**
- READ deck (proposals, RFQs, leave-behinds): current ramp (body 13pt), dense archetypes allowed.
- STAGE deck (projected talks): ≤10 slides, ~20 min, nothing under 24pt body — use ONLY the big-type
  archetypes (Statement, Thesis, KPI, Quote, Chart, dividers, Closing). Kawasaki 10/20/30 applies.

**Chart discipline (Tufte/BrightCarbon):** one chart, one message, insight headline; label series
directly, no legends; minimal gridlines; accent colour ONLY on the series that carries the message,
all else neutral grey; tables when precise lookup matters, charts when the message is a trend.

**Known conscious deviation:** card top-bars use the 4-colour brand cycle decoratively — Mint design
language, kept deliberately against the "accent = meaning only" rule.


## v2.2–v2.5 update (20 Jul 2026) — SUPERSEDES earlier ramps and conflicting rules

Marketing-approved spec (official Style Guidelines + team review rounds 1–2). Template is now
**FY27 AI-Ready v3.0.potx** (59 layouts; part numbers changed in v2.3 — always find layouts BY NAME).

**Type ramp v2.4 (final):** kickers Lato Bold UPPERCASE 14pt · content titles Lato Bold 26pt ·
body & bullets 14pt · intro lines 14pt · card/step/quadrant titles 16pt · callouts 16pt centred ·
comparison headings centred · axes 14pt · agenda title 60pt Lato Light · section/divider & team
titles Lato Light 54pt · hero titles on Content Slide 2/3/5 72pt · Body+CTA layout: title 32pt Lato
Light, subtitle Bold Italic 16pt, CTA 20pt · statement 36pt Lato Light white · quote 26pt ·
KPI numbers 34pt / labels 14pt · fine print/footers 14pt on pricing, 9.5pt floor elsewhere.

**Colour spec:** body text Mint Blue 184B9A (not grey) · kickers 439E46 on white, 89C146 on navy ·
pricing card fill 243C7A, white kicker, no green bar · roadmap bands blue 184B9A / green 439E46 /
orange F15927 / grey 626E73 · 4th card in Cards 4 grey 626E73 · matrix quadrants four distinct
tints (green/blue/grey/peach) · FAQ questions theme accent5 (orange) 16pt bold, answers tx2, title 184B9A.

**Layout changes:** Statement – Full Bleed no longer has a picture placeholder — it carries a static
Mint-branded blue background (navy fallback); just fill kicker 11, title, support 2. Agenda layouts are
solid navy (no photo). Content aligns at x 0.62" from the CI border. Closing – Next Steps: kicker
89C146, steps white, footer line green. Content – Image Right gained kicker 11 + body 12.

**Editing rule (why "Slide Master edits don't stick"):** slides inherit from each layout's
lstStyle (lvl1pPr defRPr), NOT from prompt-run formatting. Make template-level changes in the
layout XML lstStyle; keep prompt runs in sync so the master view shows the truth. Never leave
run-level colour/size overrides on sample slides — hoist them into the layout.

## v2.5 additions (20 Jul 2026)

Legacy layouts brought to standard: Agenda – 6 Items = blue gradient bg + logo, title 54pt white;
Agenda – 5 Items = white bg + grey panel, title 54pt Mint Blue, item headings 24pt; Meet the Team
names 20pt; Content Slide 2/3/4/5 titles 54pt (was 72/60); Cover – Dark title Lato Light 54pt,
subtitle Bold Italic 24pt #89C146, body white. Old versions v1.x–v2.4 live in "Archive - Old
Versions" — never use them.

## v3.0 FINAL (22 Jul 2026) — marketing sign-off build, 45 layouts

Template home going forward: Marketing SharePoint site (Mint CI Elements library) — local working copy in Mint > Marketing > PowertPoint Template.

14 layouts RETIRED (do not reference): Title Slide Option 3 & 4, About Mint Group – No B-BBEE,
Solutions Designations Badge 1, Inner Circle Member, Values, **Blue Section Divider** (use White
Section Divider or Cover – Dark for section breaks), Title and Content 1/2/5/6 (use Title and
Content 3/4/7), Agenda – 5 Items (use Agenda – 6 Items, gradient), Content Slide 2 – Split,
Content Slide 4 – Statement + CTA. Content Slide 3 – Centre title box is now full-width (fits
long headings on ≤2 lines). Sample slide 3 = White Section Divider; slide 4 = Title and Content 3.
