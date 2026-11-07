# Space pfd vs RR Table 21-4 planned

The challenge judge said pfd is the main issue. A check of riia-1 showed that pfd is only an intermediate value:
it is computed and then turned into I/N at a modelled receiver, and no pfd number reaches the API or the UI. The
likelihood–consequence chart's "pfd margin" axis label applies only to radio astronomy (spfd vs RA.769).
`data/ref/rr21_pfd_limits.json` had 3 free-text rows marked "context only", and no code read it, although the
method doc said the limits were "shown for context".

Planned in `plans/261107-1412-rr21-pfd-limit-check/` (six phases, about 3 days): a machine-evaluable Table 21-4
(piecewise in δ, plus the NGSO constellation-size rows), ingest of `srv_cls` for service matching, a deterministic
`riia/pfd.py` (Finland grid for GSO, δ sweep for NGSO, notified `c_pfd` first), and a separate `pfd_checks` result
with its own outcome, shown as a column, a filter and a notice-sheet section.

Key choices: the result is kept out of `worst_outcome` and the hazards list, because a transmitter limit is not a
receiver criterion. `model_version` stays `riia-1`, because it seeds the Monte Carlo generator, and a separate
`pfd_check_version` is added. pfd mask values are not in the IFIC `.mdb` (only `mask_lnk*` ids), so masked groups are
flagged, not evaluated. `mask_info` frequencies are in GHz while `c_pfd`'s are in MHz, and 14 of 119 `c_pfd` rows in
3074 have no reference bandwidth.

The main risk is a Table 21-4 transcription error producing a false exceedance. The plan answers it with a second
hand-entered list checked in a test, and a review status that stays pending until a person signs it off.
