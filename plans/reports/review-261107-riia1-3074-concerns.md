# Concern review: IFIC 3074, model riia-1

- `as_of` 2026-11-06. Receiver sources: `stations` (frequencies-of-interest dataset) and `generic-m4`. Readings, not a score; see `backend/src/ific/riia/review.py` for the definitions.
- Near-limit margin: 6 dB (assumption). Main beam: off-axis ≤ θ3dB/2, θ3dB ≈ 70·λ/D from the station gain (class gain when missing); pointing elevation spans the class range.
- Stations excluded: 174 broadcast transmitter licence, 5 no protected riia-1 class at the receive frequency, 58 no receive band or location.
- The CSV next to this file has the same rows plus empty `reviewer_verdict` / `reviewer_note` columns.

| Group | Meaning | Notices |
|---|---|---|
| A | Stations source: a criterion is exceeded | 23 |
| B | Stations source: a GSO position lies in a Finnish station's main beam | 0 |
| C | Stations source: within 6 dB of a criterion (near limit) | 4 |
| D | Generic population only: a criterion is exceeded | 55 |

## A. Stations source: a criterion is exceeded

### 125520111 STARERA-3 (CHN, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR named FIN (9.14).
- Exceeds: adjacent:mobile (share 100%, p95 +57.1 dB).
- Near limit: cochannel:fss_es (share 0%, p95 -4.8 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124545403 CSN-SSO (CHN, API/A, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Exceeds: cochannel:fixed (share 22%, p95 +35.5 dB); adjacent:fixed (share 100%, p95 +36.1 dB); cochannel:mobile (share 100%, p95 +50.9 dB); adjacent:mobile (share 100%, p95 +41.7 dB); cochannel:fss_es (share 100%, p95 +39.4 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125500277 GW-S (CHN, Notification, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Exceeds: cochannel:fixed (share 18%, p95 +2.7 dB); cochannel:mobile (share 100%, p95 +39.1 dB); adjacent:mobile (share 100%, p95 +33.2 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126545117 YG-1 (CHN, API/A, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Exceeds: cochannel:fixed (share 60%, p95 +7.0 dB); adjacent:fixed (share 33%, p95 +12.8 dB); cochannel:radiolocation (share 100%, p95 +34.3 dB); adjacent:radiolocation (share 100%, p95 +28.7 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125545396 GY-2 (CHN, API/A, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Exceeds: cochannel:radiolocation (share 100%, p95 +33.0 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 117520372 AST-NG-C-4 (F, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Exceeds: cochannel:mobile (share 100%, p95 +30.6 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126500107 CONNECTA IOT (TUR, Notification, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Exceeds: cochannel:mobile (share 100%, p95 +29.9 dB).
- Near limit: cochannel:fixed (share 0%, p95 -5.0 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520174 PAZ_2-A (E, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Exceeds: cochannel:radiolocation (share 100%, p95 +16.7 dB); adjacent:radiolocation (share 100%, p95 +22.3 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520174 PAZ_2-A (E, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Exceeds: cochannel:radiolocation (share 100%, p95 +16.7 dB); adjacent:radiolocation (share 100%, p95 +22.0 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 123520029 USASAT-NGSO-3X (USA, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Exceeds: cochannel:fixed (share 100%, p95 +20.3 dB); adjacent:fixed (share 78%, p95 +15.2 dB); cochannel:fss_es (share 100%, p95 +19.6 dB); adjacent:fss_es (share 100%, p95 +10.0 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 323520029 USASAT-NGSO-3X (USA, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Exceeds: cochannel:fixed (share 100%, p95 +20.3 dB); adjacent:fixed (share 40%, p95 +15.1 dB); cochannel:fss_es (share 100%, p95 +19.2 dB); adjacent:fss_es (share 100%, p95 +7.3 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520194 SECOMSAT-5-78E (E, CR/C, GSO at 78°E)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR named FIN (9.21/C).
- Exceeds: cochannel:mobile (share 100%, p95 +16.2 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520194 SECOMSAT-5-78E (E, CR/C, GSO at 78°E)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR named FIN (9.21/C).
- Exceeds: cochannel:mobile (share 100%, p95 +16.2 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520131 F-SAT-NG-15_B (F, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Exceeds: cochannel:fixed (share 80%, p95 +15.6 dB); cochannel:fss_es (share 100%, p95 +8.2 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520173 QATARGOV-G1-25.5E (QAT, CR/C, GSO at 25.5°E)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR named FIN (9.21/C).
- Exceeds: cochannel:mobile (share 100%, p95 +14.0 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520173 QATARGOV-G1-25.5E (QAT, CR/C, GSO at 25.5°E)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR named FIN (9.21/C).
- Exceeds: cochannel:mobile (share 100%, p95 +14.0 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520131 F-SAT-NG-15_B (F, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Exceeds: cochannel:fixed (share 67%, p95 +12.3 dB); cochannel:fss_es (share 100%, p95 +11.9 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 317520372 AST-NG-C-4 (F, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Exceeds: cochannel:mobile (share 100%, p95 +4.4 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 117520318 NSL-1 (ISR, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Exceeds: cochannel:fss_es (share 100%, p95 +0.7 dB); adjacent:fss_es (share 33%, p95 +0.7 dB).
- Near limit: cochannel:fixed (share 0%, p95 -4.9 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125520053 USASAT-NGSO-8F (USA, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 67%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Exceeds: cochannel:fss_es (share 67%, p95 +6.0 dB).
- Near limit: adjacent:fixed (share 0%, p95 -0.6 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 325500168 MCSAT LEO (F, Notification, NGSO)

- Stations: worst `exceeds`, max share violating 25%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Exceeds: cochannel:fixed (share 17%, p95 +1.1 dB); cochannel:fss_es (share 25%, p95 +3.3 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520184 CHINASAT-G-33.5E (CHN, CR/C, GSO at 33.5°E)

- Stations: worst `exceeds`, max share violating 17%. Generic: worst `exceeds`, max share 100%. BR named FIN (9.14).
- Exceeds: cochannel:fss_es (share 17%, p95 +16.6 dB).
- Main beam: station:616738:305 (fss_es, 18737.500–18792.500 MHz, az 176.1°, 45 dBi): satellite at az 176.2°, el 18.3°, off-axis 0.1° of θ3dB 1.0°.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520184 CHINASAT-G-33.5E (CHN, CR/C, GSO at 33.5°E)

- Stations: worst `exceeds`, max share violating 11%. Generic: worst `exceeds`, max share 100%. BR named FIN (9.14).
- Exceeds: cochannel:fss_es (share 11%, p95 +2.4 dB).
- Main beam: station:616738:305 (fss_es, 18737.500–18792.500 MHz, az 176.1°, 45 dBi): satellite at az 176.2°, el 18.3°, off-axis 0.1° of θ3dB 1.0°.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:


## C. Stations source: within 6 dB of a criterion (near limit)

### 324520214 INSAT-COM(71E) (IND, CR/C, GSO at 71°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 19%. BR named FIN (A30A#7.1, A30A#7.1-CII).
- Near limit: cochannel:fss_es (share 0%, p95 -3.2 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520214 INSAT-COM(71E) (IND, CR/C, GSO at 71°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 12%. BR named FIN (A30A#7.1, A30A#7.1-CII).
- Near limit: cochannel:fss_es (share 0%, p95 -4.7 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125545393 EUHT (CHN, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Near limit: adjacent:mobile (share 0%, p95 -5.2 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125500068 INSAT-KA68ER (IND, Notification, GSO at 68°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 11%. BR did not name FIN.
- Near limit: cochannel:fss_es (share 0%, p95 -5.7 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:


## D. Generic population only: a criterion is exceeded

### 324520183 CHINASAT-H-60.5E (CHN, CR/C, GSO at 60.5°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520183 CHINASAT-H-60.5E (CHN, CR/C, GSO at 60.5°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520204 KAZSAT-KA-67.2E-2 (KAZ, CR/C, GSO at 67.2°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520204 KAZSAT-KA-67.2E-2 (KAZ, CR/C, GSO at 67.2°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 18%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 317520318 NSL-1 (ISR, CR/C, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 7%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126545069 GD-B (CHN, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126545127 K-COMSAT (KOR, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126545119 SOLAR SENTRY (D, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 8%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126545114 PUXING-1 (CHN, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 0%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 103500417 COMPASS-80E (CHN, Notification, GSO at 80°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 303500417 COMPASS-80E (CHN, Notification, GSO at 80°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125545368 GRAVITAS (USA, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 119500051 COMPASS-80.3E (CHN, Notification, GSO at 80.3°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 319500051 COMPASS-80.3E (CHN, Notification, GSO at 80.3°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 103500416 COMPASS-58.75E (CHN, Notification, GSO at 58.75°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 303500416 COMPASS-58.75E (CHN, Notification, GSO at 58.75°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 322500245 INTELSAT7 66E (USA, Notification, GSO at 66°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 4%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 95500027 INTELSAT7 66E (USA, Notification, GSO at 66°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 6%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125545347 RLNEUTRON-1 (USA, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 96%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125512022 RGS-S-45E (RUS, Notification, GSO at 45°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125512023 RGS-S-35E (RUS, Notification, GSO at 35°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520193 MTG-EUM_9.5E (D, CR/C, GSO at 9.5°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520192 MTG-EUM_3.5E (D, CR/C, GSO at 3.5°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 309500876 CHINASAT-31 (CHN, Notification, GSO at 80°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 1%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 109500876 CHINASAT-31 (CHN, Notification, GSO at 80°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 0%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125500066 RGS-N (RUS, Notification, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR named FIN (V/11.31.1/C).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 119545232 TYSAR-01 (CHN, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 123520028 USASAT-NGSO-12 (USA, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520182 CENTISPACE-5 (CHN, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520187 INSAT-NAV-NGSO4 (IND, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520188 KPS-NGSO-A (KOR, CR/C, NGSO)

- Stations: worst `screened_out`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520191 SAILSPACE-2-A-1 (CHN, CR/C, NGSO)

- Stations: worst `screened_out`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520199 ONDOSAT (MNG, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 37%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520203 LUMIRX-1 (KOR, CR/C, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520211 METEOR-3M (RUS, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520220 USASAT-NGSO-3Y-1 (USA, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520221 NUSANTARA-NGSO-PS1 (INS, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124545392 TIANQI-3E-2 (CHN, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125512024 RGS-N (RUS, Notification, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125520047 USASAT-NGSO-8E (USA, CR/C, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125545390 USASAT-30-3 (USA, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125545395 INSIGHT-A (CHN, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125545403 CITYSEC (CHN, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 87%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126500063 USASAT-NGSO-12 (USA, Notification, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 323520028 USASAT-NGSO-12 (USA, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520182 CENTISPACE-5 (CHN, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520187 INSAT-NAV-NGSO4 (IND, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520188 KPS-NGSO-A (KOR, CR/C, NGSO)

- Stations: worst `screened_out`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520191 SAILSPACE-2-A-1 (CHN, CR/C, NGSO)

- Stations: worst `screened_out`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520192 MTG-EUM_3.5E (D, CR/C, GSO at 3.5°E)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520193 MTG-EUM_9.5E (D, CR/C, GSO at 9.5°E)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520203 LUMIRX-1 (KOR, CR/C, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520211 METEOR-3M (RUS, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520220 USASAT-NGSO-3Y-1 (USA, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520221 NUSANTARA-NGSO-PS1 (INS, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:
