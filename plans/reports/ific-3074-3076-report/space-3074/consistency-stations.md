# Consistency report: IFIC 3074, model riia-1

- Receiver source: `stations`; `as_of`: 2026-11-07.
- Notices: 196; hazards: 4508.
- Notice worst outcome: exceeds 23, not_assessed 7, meets 66, screened_out 5, not_applicable 95.

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
| broadcasting | 0 | 0 | 0 | 0 | 392 |
| fixed | 12 | 11 | 107 | 11 | 251 |
| fss_es | 13 | 0 | 26 | 0 | 353 |
| metsat_es | 0 | 0 | 0 | 0 | 392 |
| mobile | 12 | 0 | 7 | 2 | 371 |
| mss_es | 0 | 0 | 0 | 0 | 392 |
| radio_astronomy | 0 | 0 | 0 | 0 | 392 |
| radiolocation | 7 | 0 | 9 | 0 | 376 |
| radionavigation | 0 | 0 | 0 | 0 | 392 |
| rnss | 0 | 0 | 0 | 0 | 392 |

## BR findings naming Finland (technical provisions)

| ntc_id | Network | Provisions | Worst outcome | Max Tier 1 (dB) | Agrees | Why |
|---|---|---|---|---|---|---|
| 124520173 | QATARGOV-G1-25.5E | 9.21/C | exceeds | 8.0 | yes | cochannel:mobile |
| 124520179 | HISPASAT-5-52.5W | 9.11 | not_applicable | — | **miss** | never above the horizon in Finland |
| 124520184 | CHINASAT-G-33.5E | 9.14 | exceeds | 40.7 | yes | adjacent:fixed, adjacent:fss_es, cochannel:fixed, cochannel:fss_es |
| 124520194 | SECOMSAT-5-78E | 9.21/C | exceeds | 10.3 | yes | adjacent:fixed, cochannel:fixed, cochannel:mobile |
| 124520200 | UVSQ-SAT-NG | 9.21/C | not_applicable | — | **miss** | no downlink overlaps or adjoins a protected Finnish band of a riia-1 class |
| 124520212 | HOL-NGSO2-I-S | 9.21/C | not_applicable | — | **miss** | no downlink overlaps or adjoins a protected Finnish band of a riia-1 class |
| 124520214 | INSAT-COM(71E) | A30A#7.1, A30A#7.1-CII | meets | 29.7 | yes | adjacent:fixed, adjacent:fss_es, cochannel:fixed, cochannel:fss_es |
| 125520111 | STARERA-3 | 9.14 | exceeds | 62.2 | yes | adjacent:fixed, adjacent:mobile, cochannel:fss_es |
| 324520173 | QATARGOV-G1-25.5E | 9.21/C | exceeds | 8.0 | yes | cochannel:mobile |
| 324520179 | HISPASAT-5-52.5W | 9.11 | not_applicable | — | **miss** | never above the horizon in Finland |
| 324520184 | CHINASAT-G-33.5E | 9.14 | exceeds | 31.0 | yes | adjacent:fss_es, cochannel:fixed, cochannel:fss_es, cochannel:mobile |
| 324520194 | SECOMSAT-5-78E | 9.21/C | exceeds | 10.3 | yes | adjacent:fixed, cochannel:fixed, cochannel:mobile |
| 324520200 | UVSQ-SAT-NG | 9.21/C | not_applicable | — | **miss** | no downlink overlaps or adjoins a protected Finnish band of a riia-1 class |
| 324520212 | HOL-NGSO2-I-S | 9.21/C | not_applicable | — | **miss** | no downlink overlaps or adjoins a protected Finnish band of a riia-1 class |
| 324520214 | INSAT-COM(71E) | A30A#7.1, A30A#7.1-CII | meets | 29.6 | yes | adjacent:fixed, adjacent:fss_es, cochannel:fixed, cochannel:fss_es |

Misses, by worst-case value: 124520179 (—), 324520179 (—), 124520200 (—), 124520212 (—), 324520200 (—), 324520212 (—).

## Run time

- Total: 136.5 s.
- Tier 1: 0.3 s; 13 hazards screened out.
- Tier 2: 134.9 s for 193 Monte Carlo hazards.
