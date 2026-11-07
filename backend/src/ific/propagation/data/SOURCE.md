# P.1546 tabulated field strengths

`p1546_tables.npz` holds the 24 tabulated curves of Recommendation ITU-R P.1546-6 (figures 1–24: 100, 600
and 2000 MHz; land, sea, cold sea and warm sea; 1 %, 10 % and 50 % time). Values are dB(µV/m) for 1 kW
e.r.p. at 50 % locations, at 78 nominal distances (1–1000 km) and 8 nominal heights `h1` (10–1200 m).

| Array | Shape | Content |
|---|---|---|
| `distances_km` | (78,) | Nominal distances of Annex 5 Table 1 |
| `heights_m` | (8,) | 10, 20, 37.5, 75, 150, 300, 600, 1200 |
| `field` | (24, 78, 8) | `field[figure - 1, distance, height]` |
| `figures` | (24, 4) | time %, path code (1 land, 2 sea, 3 cold sea, 4 warm sea), frequency MHz, figure number |

- **Origin:** the `exceltables` and `figure_rec` literals in `matlab/P1546FieldStrMixed.m` of
  https://github.com/eeveetza/p1546, commit `0e4263999ce055100f42257c2aafbac96ac630af` (P1546 package
  version 6.2, the reference approved by ITU-R WP 3K). The 10th column of the reference tables, the
  free-space maximum, is not stored: the engine computes it from Annex 5 section 2.
- **Extraction:** parsed verbatim, with no rounding.
- **SHA-256:** `963f68492e92d793cf699ff063192b2563db89468a8170e2f4e613b09df07727`
- **Spot checks:** `tests/test_p1546.py::test_tabulated_values` (figures 1, 4 and 9 at 1 km, 10 m).
