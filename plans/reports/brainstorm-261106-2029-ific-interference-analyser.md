# Brainstorm contract — IFIC interference analyser (Traficom / Since AI 2026)

Source brief: `Problem.pdf`. Stack decided by user: Python (uv) + DuckDB + FastAPI backend, Vite/React frontend.

## Outcome

A local web app that ingests any ITU BR IFIC issue (Space `.mdb`, Terrestrial `.mdb`), runs a deterministic
Finland-relevance and interference screening, and presents ranked findings that an expert can review. Each finding
links back to its source notice, the regulation or standard clause used, the calculation inputs and the result.
For each concern, the app drafts a letter to the notifying administration for expert review.
It also exports the result files for Space IFIC 3074 and Terrestrial IFIC 3076 that the hackathon requires.

## Evidence (inspected 2026-11-06)

| Source | Finding |
|---|---|
| `ific3074.mdb` | 196 notices: `9.1/IA` (API/A) 50, `9.6` (CR/C) 76, `11.2` (notification) 65, `RS49` 5. Key tables: `notice`, `grp`, `freq`, `c_pfd`, `geo`, `non_geo`, `srv_area`, `es_ctry`, `mask_info`, `e_stn`. |
| `ific3083.mdb` | 168 notices with the same schema. Usable as a second space issue for regression and trend checks. |
| AP30/30A/30B | **No AP30-family provisions found** in 3074 or 3083 `notice.prov`. They are probably published in a separate SPS/Part B dataset, which needs confirmation. |
| `brific3076.mdb` | 4,058 `fxm_terra` rows. `intent` = ADD 2905 / MODIFY 163 / SUPPRESS 413 / RECORDED 576. New, modified and withdrawn can therefore be derived **within one issue**; diffing against an adjacent issue is extra. Neighbour admins present: RUS 313 (FX 188, ML 68, FB 57). |
| `data/api/taajuusjakotaulukko.{csv,json}` | Finnish frequency allocation table with Hz band limits, service, sub-band usage and station class. |
| `data/m4/*` | M4 regulation text and PDF in English, plus explanatory notes. |
| Tooling | `mdbtools`, `uv`, `bun` and `node` are installed locally. |

## Constraints

- Hackathon timebox: 6–8 Nov 2026, with the demo on Sunday.
- Calculations are deterministic and reproducible. The same input must produce the same findings, with every assumption and model parameter shown.
- The LLM never decides whether something is relevant or exceeds a limit. It only summarises, ranks the explanation and drafts letters, and every claim must cite a finding ID or source reference. The app must stay fully usable without an LLM, falling back to template-based drafts.
- Raw `.mdb` files (up to 273 MB) and derived DuckDB files are not committed to git.
- ITU desktop tools (SpaceCom, GIBC) are Windows-only and are not part of the pipeline. They may only be used by hand to cross-check results.
- One core pipeline with two domain adapters, space and terrestrial. The brief names both variants, so a shared seam is justified.

## Non-goals

- A full reimplementation of the ITU coordination examination (Appendix 5 ΔT/T, EPFD Article 22 validation, AP30 OEPM/EPM computation).
- Automatic fetching or scraping of IFICs from the ITU portal beyond the specified ingest-a-file flow. A "drop a file / point at a URL" ingest is enough.
- Authentication, multi-user support, cloud deployment and production hardening.
- Terrestrial services other than land mobile (FX, broadcasting, LF/MF) in the side quest.
- M15 and CEPT ECO ingestion at first. They are optional enrichment, added only if time remains.

## Architecture (chosen direction)

```
ingest (mdb-export → DuckDB, one schema per issue, provenance = issue/table/key)
  → normalise (domain adapter → common `Assignment` rows: adm, freq_min/max Hz, location/footprint, power, class)
  → screen (deterministic rules: frequency overlap with FI table & special-interest list; geographic relevance)
  → calculate (space: pfd at Finnish test points vs RR Art.21 / c_pfd masks; terrestrial: P.1546 field strength vs T/R 25-08)
  → score & rank (severity = margin over limit × FI usage importance)
  → explain & draft (LLM optional; templated fallback; citations mandatory)
  → API (FastAPI) → UI (React: issue list, findings table, evidence panel, map, draft editor) + export (JSON/CSV/Markdown)
```

## Trade-offs

| Approach | Depends most on | Fails first when |
|---|---|---|
| **A. Deterministic rules and calculations, with an LLM narration layer (chosen)** | The MDB fields being enough to compute pfd and field strength (power, gain, bandwidth, orbit or site) | Notices lack power or gain data. Mitigation: flag the finding as "insufficient data, overlap only" and make that explicit rather than guessing. |
| B. LLM/RAG agent reads notices and judges relevance | LLM accuracy on numeric, unit-heavy records | Immediately on reproducibility (criterion A) and false positives (criterion D). Results are not auditable. |
| C. Drive the ITU tools (SpaceCom/GIBC) for the calculations | Having a Windows host and scripting those tools | Demo machine is macOS and the tools cannot be scripted from the web app. Only usable for manual validation. |

Evolutionary-design check: space and terrestrial share ingest, the overlap screen, scoring, the evidence model,
drafting and the UI. They differ in normaliser, geography test and propagation/pfd model. So the shared core
owns the `Assignment`/`Finding`/`Evidence` contracts, and each adapter implements `normalise`, `is_relevant` and `calculate`.
No plugin framework beyond that.

Better approaches: none. The recommended direction is the one requested. The table and the evidence show that
Python suits the numeric work, DuckDB reads mdbtools CSV directly, and FastAPI plus React gives the reviewer UI needed for criterion C.

## Acceptance criteria

1. `uv run ific ingest <file.mdb>` loads any space or terrestrial IFIC into DuckDB. Proven on 3074, 3083 and 3076.
2. `uv run ific analyse <issue>` writes deterministic findings. Two runs produce byte-identical output, checked by a test.
3. Space 3074: every finding carries notice ID, admin, provision (API/A, CR/C, notification), overlapping FI band(s) with M4/table row cite, and a pfd calculation where data allows. Inputs, formula, Finnish test point and limit source are shown.
4. Terrestrial 3076: land-mobile (FB/ML and related) assignments are classified as new, modified or withdrawn and filtered to those relevant to Finland. Each has a P.1546 field strength at the border or test points compared to the T/R 25-08 trigger, with model parameters (frequency, height, time %, path type) listed.
5. Findings are ranked by severity, and each has a draft letter naming the counterparty administration. The LLM draft is used when configured, otherwise the template.
6. A trends/anomalies view for neighbour administrations shows counts by band, station class, bandwidth and geography for at least the 3076 data.
7. The web UI runs locally (`make dev` or similar). It covers issue selection, the ranked findings table, an evidence panel with source fields and citations, a map of sites or footprints, and an editable draft.
8. Submission exports exist for 3074 and 3076 (CSV and JSON, plus a Markdown report).
9. Unit tests cover the pfd and P.1546 calculations against published reference values. P.1546 is checked against the ITU tabulated curves or a published worked example.

## Risks and unknowns

- **P.1546 implementation** (interpolation over the tabulated curves, height/distance/frequency/time corrections) is the riskiest calculation work. Mitigation: implement the land-path core first and add the mixed-path and sea corrections later.
- **Missing pfd inputs** for many notices. They degrade to overlap-only findings with an explicit data gap.
- **Synthetic special-interest XLS** is not in the repo yet and must come from the SinceAI platform.
- **AP30/30A/30B data source** is unclear. See the questions below.
- The MDB date format (`MM/DD/YY`) and code tables (`ref_*`, admin codes such as `F`=France and `S`=Sweden) need careful decoding. Wrong admin decoding would mean the wrong counterparty in drafts.

## Unresolved questions

1. Where do the AP30/30A/30B notices come from, since they are absent from the 3074/3083 Space `.mdb`? Ask Traficom on Saturday at the Space IFIC slot (10–11).
2. Which LLM provider and key can the demo use? The default is Claude, with the template fallback when no key is set.
3. Is an adjacent terrestrial issue (3075 or 3077) available? It is not required, because `intent` covers new/modified/withdrawn.
4. What exact format do the 3074/3076 result files need, and is there a submission template?
