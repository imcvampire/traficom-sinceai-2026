# Code review: riia-1 backend (risk-informed interference assessment)

Date: 2026-11-07. Read-only review; no source or plan files were changed.

## Outcome

The test suite passes (157 tests, 7.5 s). The Tier 1 ≥ Tier 2 invariant holds as the code is written today. I found
one data-units bug that inflates every notified pfd by 30 dB. I also found a Tier 2 pruning bug that undercounts
satellites in mixed-altitude constellations (confirmed by a reproduction), and a dead code path that means the
height distributions are never drawn. The remaining findings are concurrency edges, an injection surface in
ingest, and small contract drift.

## Scope

- Files: `backend/src/ific/ingest.py`, `backend/src/ific/riia/*.py`, `backend/src/ific/api.py` (risk routes,
  lifespan), `backend/src/ific/cli.py` (ingest/assess/assess-sensitivity), and tests `test_ingest.py`,
  `test_riia_*.py`, `riia_fixtures.py`. About 4,700 lines.
- Spec, contract and plan: `docs/interference-risk-assessment.md`,
  `plans/261106-2255-sat-severity-scoring/{api-contract.md,plan.md,phase-0*.md}`.
- Evidence: `uv run pytest -q`, small numpy reproductions, and `mdb-export` of `ific3074.mdb` / `ific3083.mdb`
  (read-only). `var/db/ific.duckdb` was not touched.
- Updated plans: none (read-only review).

## Findings

### Critical

**C1. `c_pfd.bdwdth` is in kHz but is subtracted as Hz, so the notified pfd density is 30 dB too high.** CONFIRMED.
- Where: `riia/assess.py:150`, `pfd - 10 * math.log10(bw if bw else bn)`.
- Evidence: the 3074 rows match RA.769 only if `bdwdth` is in kHz. Three examples:
  - `116500154`, 4990–5000 MHz: −171 dBW/m² in `bdwdth=10000`. With kHz this is −171 − 70 = −241 dB(W/m²/Hz),
    which is exactly the RA.769 4995 MHz threshold in `receiver_classes.json`.
  - `113520154`, 42.5–43.5 GHz: −137 dBW/m² in `1000000`, i.e. −227 dB(W/m²/Hz) over 1 GHz, which matches RA.769.
  - `116500154` seq 2, 5030–5150 MHz: −124.5 dBW/m² in `150`, which matches the RR 5.443C MLS limit in 150 kHz.
- `grp.bdwdth` uses kHz too (`_bn_hz` multiplies it by 1e3, and 14000 corresponds to a 14 MHz group). The
  fallback `bn` is in Hz, so only the `bw` branch is wrong.
- Failure: any group with a notified c_pfd gets a density, and therefore an I/N or spfd margin, that is 30 dB too
  high in both Tier 1 and Tier 2. This produces false `exceeds`, notably for radio astronomy. The plan counts 49
  such notices in 3074.
- Fix: `pfd - 10 * math.log10(bw * 1e3 if bw else bn)`. Add a fixture row with a non-empty `bdwdth` and a
  hand-computed density test.

### High

**H1. The Tier 2 NGSO candidate prefilter uses the smallest orbit radius, so it drops visible satellites in
higher shells.** CONFIRMED by reproduction.
- Where: `riia/hazards.py:326`, `lam = horizon_central_angle_deg(const.radius_km.min(), ...)`.
- The coverage half-angle grows with radius: about 22° at 500 km, 32.7° at 1,200 km and 63.7° at 8,000 km. The
  cut is therefore too tight for every shell above the lowest one.
- The filter works per time batch, with `batch = 2e6 // (ns * size/10)`. For a large constellation over the
  Finland grid the batch is only a few time samples, so a satellite can be visible at 23°–63° from the centroid
  and still be pruned.
- Reproduction: 100 planes × 50 satellites at 550 km plus one plane of 10 at 8,000 km, 900 Finnish sites, T = 40
  (batch = 4). Brute-force visible (site, satellite, time) triples: 5,802,154. `_site_sums` counted 5,735,691, so
  66,463 were lost from the MEO plane.
- Real data: in 3074, 41 of 106 orbit sets have more than one altitude.
- Effect: Tier 2 understates I/N for mixed-altitude systems. The Tier 1 bound is unaffected, but `exceeds` can
  turn into `meets`.
- Fix: use `const.radius_km.max()` (or a per-satellite cut). Add a regression test that compares `_site_sums`
  with a brute-force count on a two-shell constellation.

**H2. Receiver height distributions are never sampled; every site is at 0 m.** CONFIRMED by code trace.
- Where: `riia/assess.py:440` sets `height_m=np.nan_to_num(pop.site_h[sites], nan=0.0)`. `hazards._draw`
  (`hazards.py:278-280`) only draws where `given` is NaN, so the call at `hazards.py:373` always returns zeros.
- Every class declares a `height_m` distribution (fixed 10–60 m, broadcasting 10 m, radio astronomy 10 m, …).
  The hazard `inputs` advertise "height_m distribution U(10, 60)", but none of it reaches the geometry.
- Effect: the output contradicts its stated inputs. The numerical effect is small (tens of metres over slant
  ranges of hundreds of km or more), but the run is not doing what it reports.
- Fix: keep NaN in `HazardReceivers.height_m` and draw from it in Tier 2. Then Tier 1 must use the upper end of
  the distribution, not `hr.height_m.max()` (`hazards.py:256`): a higher site has a shorter minimum range, and
  without that change the bound breaks once draws work. Fixing this changes RNG consumption and so every Tier 2
  number, which needs a fixture refresh.

**H3. The passive (spfd) consequence adds the full receiver main-beam gain to an RA.769 threshold.** PLAUSIBLE;
needs a spec decision.
- Where: `hazards.py:185` (passive branch) combined with `L`/`M`, which include `G_r(θ)`, and Tier 1 `+ gmax`.
- RA.769 spfd thresholds assume a 0 dBi receiving antenna. The M.1583/S.1586 practice normalises by
  `G_r(θ)/G_r,max`. For RA.1631 with 60 dBi, the code adds up to +60 dB in the main beam.
- This matches the module docstring formula, but the spec (`docs/...:95, 112`) defines the passive metric only as
  "received spfd minus threshold", so the code may not do what the spec intends.
- Fix (if confirmed): for `metric == "spfd_margin"`, subtract `cls.gain_dbi` from `pair_terms`, or use
  `G_r − G_max` in the gain function, and apply the same change in Tier 1.

### Medium

**M1. The c_pfd row used for a group is the first one that overlaps, not the strongest.** CONFIRMED.
- Where: `assess.py:148-155` takes the first match with `next(...)`, and the query at `assess.py:97-101` has no
  ORDER BY.
- Example: `113520154` has three rows over 42.5–43.5 GHz with densities of −227, −210 and −173 dB(W/m²/Hz), and
  the first one (−227) is taken. That is 54 dB below the strongest.
- The selection also depends on scan order, which is a determinism risk if `preserve_insertion_order` or the
  thread count changes.
- Fix: `ORDER BY ntc_id, seq_no` and take `max(...)` over the overlapping rows, or the row whose band best covers
  the group.

**M2. A missing satellite gain defaults to 0 dBi but is labelled "peak gain".** PLAUSIBLE.
- Where: `assess.py:166`. When the `s_beam` row is missing, or `gain` is NULL, `gain_dbi=0.0` and
  `gain_assumed=True` are set. That attaches the `peak_gain` assumption text ("use peak gain toward every
  receiver").
- Effect: Tier 1 is then not a worst case for those groups, and the label is misleading. The plan says 5 of 2,304
  beams have no gain in 3074.
- Fix: mark these groups `not_assessed` ("satellite gain not notified"), or use a stated conservative default
  with its own assumption id.

**M3. Possible DDL/SQL injection through `.mdb` column names in ingest.** PLAUSIBLE.
- Where: `ingest.py:177-178, 190, 192`. Header names from the exported CSV are interpolated into
  `CREATE TABLE ... "{c}"`, `ALTER TABLE ... "{col}"` and `columns = {'{c}': ...}`.
- The `.mdb` comes from a downloaded ZIP (the watcher). A column name containing `"` or `'` breaks the quoting.
- Fix: reject headers that do not match `^[A-Za-z0-9_]+$` with an `IngestError`, or escape `"`→`""` and
  `'`→`''`.

**M4. A POST can re-ingest an issue while a job for that same issue is reading it.** PLAUSIBLE.
- Where: `api.py:257-265`. The `running` check, `ensure_issue` and `jobs.start` are three separate steps.
- Scenario: two POSTs arrive together. Both pass the check. A ingests and starts its job. If the `.mdb` changed
  in the meantime (for example after a watcher re-download), B re-ingests while A's job runs.
  `assess_issue` reads `space.*` in several separate statements (`_load_notices`, `_load_geometry`, `_pairs`), so
  A can mix old and new rows. Concurrent first-time ingests can also hit DuckDB catalog or PK conflicts, which
  surface as a misleading 422.
- Fix: run the ingest inside the job thread under the per-key lock, or acquire the key lock in the handler
  before `ensure_issue`. Optionally read everything in one explicit transaction in `assess_issue`.

**M5. Shutdown can close the connection under a running job.** PLAUSIBLE.
- Where: `jobs.py:142-145`, `api.py:46-48`. `_stop` is only checked in `progress`, which runs once per notice. A
  single notice with many Tier 2 hazards can take longer than 10 s.
- `shutdown` joins each thread for 10 s in turn, then `con.close()` runs while the daemon thread may still be
  using its cursor. The likely result is a DuckDB error, and possibly a crash on interpreter exit. The final
  `save_job` will also fail. Restart recovery marks the job failed, so no data is lost, but the shutdown is not
  clean.
- Fix: check `_stop` inside the hazard loop as well, use one overall deadline, and skip `con.close()` (or log it)
  while threads are alive.

**M6. Exceedance strictness differs between spec and code.** CONFIRMED.
- The spec defines `F_r(x) = P(consequence ≥ x)` and `L_p(x) = share with X_r(p) ≥ x` (`docs/...:151-153`).
- `curves.py` is strict (`>`) throughout, and the tests pin the strict behaviour.
- The practical effect is nil for continuous values, but the documents disagree. Align the doc with the code, or
  change the code.

### Low

- **L1.** `JobRunner._jobs` is changed in `start()` without `_registry`, while `running()` iterates over it from
  another threadpool thread (`/api/health`). This can raise "dictionary changed size during iteration". Guard
  both with `_registry`. PLAUSIBLE.
- **L2.** An `IngestError` can leak absolute paths into the 422 `detail`:
  - `ingest.py:216` builds `f"IFIC {ific_no}: {path} not found"`.
  - `ingest.py:250` wraps DuckDB errors, which name the temporary CSV path.
  - Fix: use `_display(path)` and strip paths from the wrapped message.
  - Separately, `/api/health` already returns `db.path` as an absolute path (this predates the risk routes).
  - PLAUSIBLE.
- **L3.** `any_value(sat_name)` / `any_value(stn_name)` in `assess.py:88` can pick a different row between runs
  when a notice has `com_el` rows with different names. `sat_name` is part of the canonical export, so the export
  may not be byte-identical. Use `min()` or `arg_min(sat_name, seq_no)`. PLAUSIBLE.
- **L4.** Contract drift between `api-contract.md` and the code:
  - `services_assessed` counts only `tier == 2` hazards (`assess.py:723-725`), while the contract says "any
    quantified hazard".
  - `RegulatorySummaryOut.stage` and `NoticeSummaryOut.ntc_type` are typed `str`, while the contract uses
    literals (`Stage`, `'G'|'N'|'S'`).
  - `HazardOut` drops the stored `tier2_max_db`. That is allowed by the contract, but it is useful for review.
- **L5.** Dead code: `dlon` in `_gso_site_range_min` (`hazards.py:225, 231`). The GSO "nearest longitude" logic is
  duplicated in `visible_anywhere`; extract one helper.
- **L6.** When only `pwr_ds_max` is present and the designator bandwidth is missing, `p = pds + 0`
  (`assess.py:136`). This understates the Appendix 3 spurious threshold `43 + P`. Compute `p` after the
  `bn` fallback at line 143.

## Checked and correct

- **Tier 1 bound.** `c = db_add(a+L, b+M)` with `L ≤ n_vis·G_max/SP(d_min)` and `M ≤ n_vis·G_max` gives
  `max(db_add(a−SP(d_min), b)) + G_max + 10·log n_vis`.
  - `max_visible` (floor(2λn/360)+1 per plane, λ at 0° elevation) is a valid bound, because every class has
    `min_elev ≥ 0`.
  - `min_range_km` (latitude gap to the inclination band) is a valid bound.
  - S.672 and all receiver patterns are capped at peak gain.
  - Mixed calculated and notified pfd is bounded term by term.
  - The bound will break if H2 is fixed without the Tier 1 change.
- **Quantile index.** `exceeded_for` is exact for strict `>` semantics. A brute-force check over every T from 20
  to 10⁶ for p ∈ {20, 2, 1, 0.0125} found no floating-point floor error.
- **Units.**
  - MHz→Hz conversions for `grp`, `c_pfd` frequencies and RA.769 points are correct.
  - `grp.bdwdth` in kHz, `pep_max − 10·log B_n`, aperture λ²/4π, noise kT₀+10·log B+NF (kT₀ = −203.98) and
    `psi0 = (maj+min)/4` are correct.
  - In the adjacent I/N case, `db_add(PSD·b_ov·mask, PSD·B_n·ACS)` is a correct ACIR-style sum.
- **Seeding and ordering.** `rng_for` and `_pairs` ORDER BY are deterministic. Store writes are atomic per issue,
  and failures roll back. SQL elsewhere is parameterised; f-strings use only constant table and column names.

## Recommended actions (in order)

1. Fix C1 (kHz) and add a fixture with a `c_pfd.bdwdth`.
2. Fix H1 (`radius_km.max()`) and add a brute-force regression test.
3. Fix H2 together with the matching Tier 1 height bound, then regenerate fixtures and consistency reports.
4. Decide H3 with the spec owner.
5. Fix M1 and M2, then M3, M4 and M5.

## Metrics

- Tests: 157 passed. No coverage run.
- Lint and type checks: not run (read-only review; not requested).

## Unresolved questions

- H3: should the RA spfd margin use a gain normalised to 0 dBi (G_r − G_max)?
- For a c_pfd row with empty `bdwdth`, is the reference bandwidth the carrier B_n (the current assumption)? Or is
  it per notified group or 1 MHz, as for RNSS 1164–1215 MHz?
- Should c_pfd rows that are RR limits (with `ra_stn_type`) replace the calculated pfd at all? This review flags
  only the code behaviour, not the modelling.

Status: DONE_WITH_CONCERNS
Summary: Tests pass and the Tier 1 ≥ Tier 2 invariant holds. Three issues need fixing first: c_pfd reference
bandwidths in kHz are treated as Hz (+30 dB), the NGSO prefilter undercounts higher shells (reproduced), and
height distributions are never applied.
