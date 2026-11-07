# Consistency report: IFIC 3074, model riia-1

- Receiver source: `generic-m4`; `as_of`: 2026-11-07.
- Notices: 196; hazards: 4508.
- Notice worst outcome: exceeds 82, not_assessed 9, meets 36, screened_out 5, not_applicable 64.

## Checks

| Check | Result |
|---|---|
| Tier 1 worst case ≥ Tier 2 maximum, every Tier 2 hazard | pass (0 violations) |
| No `exceeds` for suppressions or never-visible notices | pass (0 notices) |
| BR identified Finland under a technical provision → at least one live hazard | 9 of 15 agree, 6 misses |
| pfd `exceeds` ⇔ some Table 21-4 check has a positive margin | pass (0 notices) |

- pfd vs RR Table 21-4: exceeds 47, not_assessed 31, meets 50, screened_out 0, not_applicable 68.

## Outcomes per service class (quantified modes)

| Class | exceeds | not_assessed | meets | screened_out | not_applicable |
|---|---|---|---|---|---|
| broadcasting | 20 | 0 | 2 | 4 | 366 |
| fixed | 68 | 9 | 99 | 8 | 208 |
| fss_es | 59 | 0 | 17 | 2 | 314 |
| metsat_es | 6 | 0 | 0 | 0 | 386 |
| mobile | 32 | 10 | 23 | 60 | 267 |
| mss_es | 60 | 4 | 11 | 25 | 292 |
| radio_astronomy | 37 | 0 | 0 | 0 | 355 |
| radiolocation | 38 | 2 | 39 | 7 | 306 |
| radionavigation | 29 | 2 | 5 | 35 | 321 |
| rnss | 29 | 0 | 5 | 8 | 350 |

## BR findings naming Finland (technical provisions)

| ntc_id | Network | Provisions | Worst outcome | Max Tier 1 (dB) | Agrees | Why |
|---|---|---|---|---|---|---|
| 124520173 | QATARGOV-G1-25.5E | 9.21/C | exceeds | 103.2 | yes | adjacent:fixed, adjacent:fss_es, adjacent:radio_astronomy, adjacent:radionavigation |
| 124520179 | HISPASAT-5-52.5W | 9.11 | not_applicable | — | **miss** | never above the horizon in Finland |
| 124520184 | CHINASAT-G-33.5E | 9.14 | exceeds | 140.1 | yes | adjacent:broadcasting, adjacent:fixed, adjacent:fss_es, adjacent:mobile |
| 124520194 | SECOMSAT-5-78E | 9.21/C | exceeds | 22.3 | yes | adjacent:fixed, adjacent:fss_es, adjacent:radionavigation, cochannel:fixed |
| 124520200 | UVSQ-SAT-NG | 9.21/C | not_applicable | — | **miss** | no downlink overlaps or adjoins a protected Finnish band of a riia-1 class |
| 124520212 | HOL-NGSO2-I-S | 9.21/C | not_applicable | — | **miss** | no downlink overlaps or adjoins a protected Finnish band of a riia-1 class |
| 124520214 | INSAT-COM(71E) | A30A#7.1, A30A#7.1-CII | exceeds | 30.0 | yes | adjacent:fixed, adjacent:fss_es, cochannel:fixed, cochannel:fss_es |
| 125520111 | STARERA-3 | 9.14 | exceeds | 69.3 | yes | adjacent:fixed, adjacent:mobile, adjacent:mss_es, adjacent:rnss |
| 324520173 | QATARGOV-G1-25.5E | 9.21/C | exceeds | 19.3 | yes | adjacent:radionavigation, cochannel:fixed |
| 324520179 | HISPASAT-5-52.5W | 9.11 | not_applicable | — | **miss** | never above the horizon in Finland |
| 324520184 | CHINASAT-G-33.5E | 9.14 | exceeds | 140.1 | yes | adjacent:fixed, adjacent:mobile, adjacent:mss_es, adjacent:radio_astronomy |
| 324520194 | SECOMSAT-5-78E | 9.21/C | exceeds | 22.3 | yes | adjacent:fixed, adjacent:fss_es, adjacent:radionavigation, cochannel:fixed |
| 324520200 | UVSQ-SAT-NG | 9.21/C | not_applicable | — | **miss** | no downlink overlaps or adjoins a protected Finnish band of a riia-1 class |
| 324520212 | HOL-NGSO2-I-S | 9.21/C | not_applicable | — | **miss** | no downlink overlaps or adjoins a protected Finnish band of a riia-1 class |
| 324520214 | INSAT-COM(71E) | A30A#7.1, A30A#7.1-CII | exceeds | 29.3 | yes | adjacent:fixed, adjacent:fss_es, cochannel:fixed, cochannel:fss_es |

Misses, by worst-case value: 124520179 (—), 324520179 (—), 124520200 (—), 124520212 (—), 324520200 (—), 324520212 (—).

## Run time

- Total: 231.8 s.
- Tier 1: 3.9 s; 149 hazards screened out.
- Tier 2: 225.3 s for 579 Monte Carlo hazards.
