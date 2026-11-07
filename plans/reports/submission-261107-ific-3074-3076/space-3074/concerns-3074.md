# Concern review: IFIC 3074, model riia-1

- `as_of` 2026-11-07. Receiver sources: `stations` (frequencies-of-interest dataset) and `generic-m4`. Readings, not a score; see `backend/src/ific/riia/review.py` for the definitions.
- pfd: worst pfd on Finnish territory against RR Article 21, Table 21-4 (Edition of 2024); the transcription in `data/ref/rr21_pfd_limits.json` is pending review. Group P takes precedence; the I/N readings of those notices are listed under them.
- Near-limit margin: 6 dB (assumption). Main beam: off-axis ≤ θ3dB/2, θ3dB ≈ 70·λ/D from the station gain (class gain when missing); pointing elevation spans the class range.
- Stations excluded: 174 broadcast transmitter licence, 5 no protected riia-1 class at the receive frequency, 58 no receive band or location.
- The CSV next to this file has the same rows plus empty `reviewer_verdict` and `reviewer_note` columns.

| Group | Meaning | Notices |
|---|---|---|
| P | pfd exceeds an RR Table 21-4 limit on Finnish territory | 47 |
| A | Stations source: a criterion is exceeded | 8 |
| B | Stations source: a GSO position lies in a Finnish station's main beam | 0 |
| C | Stations source: within 6 dB of a criterion (near limit) | 1 |
| D | Generic population only: a criterion is exceeded | 35 |

## P. pfd exceeds an RR Table 21-4 limit on Finnish territory

### 124545403 CSN-SSO (CHN, API/A, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +37.2 dB.
  - t21-4-2500-2520-mss grp 125749513 (1/1 groups exceed): pfd -87.8 vs limit -125.0 dB(W/m²) in 1000 kHz at δ 90.0°, margin +37.2 dB, calculated
  - t21-4-2520-2535-mss grp 125749513 (1/1 groups exceed): pfd -87.8 vs limit -125.0 dB(W/m²) in 1000 kHz at δ 90.0°, margin +37.2 dB, calculated
  - t21-4-32300-33000-iss grp 124747321 (2/2 groups exceed): pfd -111.7 vs limit -135.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +23.3 dB, calculated
  - t21-4-4500-4800-fss-metsat-mss-sr grp 125749526 (1/1 groups exceed): pfd -118.7 vs limit -142.0 dB(W/m²) in 4 kHz at δ 90.0°, margin +23.3 dB, calculated
  - t21-4-24450-24750-fss-bss-eess-iss-sr grp 124747319 (2/2 groups exceed): pfd -96.2 vs limit -105.0 dB(W/m²) in 1000 kHz at δ 90.0°, margin +8.8 dB, calculated
- Exceeds: cochannel:fixed (share 22%, p95 +35.5 dB); adjacent:fixed (share 100%, p95 +36.1 dB); cochannel:mobile (share 100%, p95 +50.9 dB); adjacent:mobile (share 100%, p95 +41.7 dB); cochannel:fss_es (share 100%, p95 +39.4 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126545117 YG-1 (CHN, API/A, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +36.9 dB.
  - t21-4-25250-27500-fss-bss-eess-iss-sr grp 126662641 (2/2 groups exceed): pfd -68.1 vs limit -105.0 dB(W/m²) in 1000 kHz at δ 90.0°, margin +36.9 dB, calculated
- Exceeds: cochannel:fixed (share 60%, p95 +7.0 dB); adjacent:fixed (share 33%, p95 +12.8 dB); cochannel:radiolocation (share 100%, p95 +34.3 dB); adjacent:radiolocation (share 100%, p95 +28.7 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520183 CHINASAT-H-60.5E (CHN, CR/C, GSO at 60.5°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +27.2 dB.
  - t21-4-32300-33000-iss grp 124793965 (2/2 groups exceed): pfd -105.4 vs limit -132.6 dB(W/m²) in 1000 kHz at δ 7.4°, margin +27.2 dB, calculated
  - t21-4-42000-42500-fss-bss-gso grp 124794066 (3/3 groups exceed): pfd -106.2 vs limit -123.8 dB(W/m²) in 1000 kHz at δ 7.4°, margin +17.6 dB, calculated
  - t21-4-37500-40000-fss-mss-gso grp 124794058 (5/5 groups exceed): pfd -107.2 vs limit -123.8 dB(W/m²) in 1000 kHz at δ 7.4°, margin +16.6 dB, calculated
  - t21-4-40500-42000-fss-bss-gso grp 124794066 (3/4 groups exceed): pfd -106.2 vs limit -117.6 dB(W/m²) in 1000 kHz at δ 7.4°, margin +11.4 dB, calculated
  - t21-4-10700-11700-fss-gso grp 124794027 (10/12 groups exceed): pfd -142.2 vs limit -148.8 dB(W/m²) in 4 kHz at δ 7.4°, margin +6.6 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520184 CHINASAT-G-33.5E (CHN, CR/C, GSO at 33.5°E)

- Stations: worst `exceeds`, max share violating 11%. Generic: worst `exceeds`, max share 100%. BR named FIN (9.14).
- pfd vs Table 21-4: `exceeds`, max margin +23.2 dB.
  - t21-4-32300-33000-iss grp 124793578 (2/2 groups exceed): pfd -105.3 vs limit -128.6 dB(W/m²) in 1000 kHz at δ 11.4°, margin +23.2 dB, calculated
  - t21-4-42000-42500-fss-bss-gso grp 124793684 (8/8 groups exceed): pfd -106.1 vs limit -118.4 dB(W/m²) in 1000 kHz at δ 11.4°, margin +12.3 dB, calculated
  - t21-4-37500-40000-fss-mss-gso grp 124793676 (10/10 groups exceed): pfd -107.1 vs limit -118.4 dB(W/m²) in 1000 kHz at δ 11.4°, margin +11.3 dB, calculated
  - t21-4-40500-42000-fss-bss-gso grp 124793684 (8/9 groups exceed): pfd -106.1 vs limit -113.6 dB(W/m²) in 1000 kHz at δ 11.4°, margin +7.4 dB, calculated
  - t21-4-13400-13650-fss-gso grp 124796220 (12/13 groups exceed): pfd -149.7 vs limit -154.4 dB(W/m²) in 4 kHz at δ 11.4°, margin +4.7 dB, calculated
- Exceeds: cochannel:fss_es (share 11%, p95 +2.4 dB).
- Main beam: station:616738:305 (fss_es, 18737.500–18792.500 MHz, az 176.1°, 45 dBi): satellite at az 176.2°, el 18.3°, off-axis 0.1° of θ3dB 1.0°.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124545392 TIANQI-3E-2 (CHN, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +22.5 dB.
  - t21-4-32300-33000-iss grp 124736654 (1/1 groups exceed): pfd -112.5 vs limit -135.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +22.5 dB, calculated
  - t21-4-1700-1710-sr-so-eess-metsat grp 125758995 (0/1 groups exceed): pfd -154.5 vs limit -154.0 dB(W/m²) in 4 kHz at δ 5.0°, margin -0.5 dB, calculated
  - t21-4-2200-2300-sr-so-eess-metsat grp 125784974 (0/1 groups exceed): pfd -156.9 vs limit -154.0 dB(W/m²) in 4 kHz at δ 5.0°, margin -2.9 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125500066 RGS-N (RUS, Notification, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR named FIN (V/11.31.1/C).
- pfd vs Table 21-4: `exceeds`, max margin +21.4 dB.
  - t21-4-7250-7900-fss-metsat-mss-sr grp 125638799 (12/12 groups exceed): pfd -120.6 vs limit -142.0 dB(W/m²) in 4 kHz at δ 90.0°, margin +21.4 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125545347 RLNEUTRON-1 (USA, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 96%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +20.3 dB.
  - t21-4-2200-2300-sr-so-eess-metsat grp 125748048 (8/8 groups exceed): pfd -123.7 vs limit -144.0 dB(W/m²) in 4 kHz at δ 90.0°, margin +20.3 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 325500168 MCSAT LEO (F, Notification, NGSO)

- Stations: worst `exceeds`, max share violating 25%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +16.4 dB.
  - t21-4-17700-19300-fss-ngso grp 325865757 (32/32 groups exceed): pfd -115.7 vs limit -132.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +16.4 dB, calculated
- Exceeds: cochannel:fixed (share 17%, p95 +1.1 dB); cochannel:fss_es (share 25%, p95 +3.3 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520204 KAZSAT-KA-67.2E-2 (KAZ, CR/C, GSO at 67.2°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +15.9 dB.
  - t21-4-37500-40000-fss-mss-gso grp 124725837 (12/12 groups exceed): pfd -110.3 vs limit -126.1 dB(W/m²) in 1000 kHz at δ 5.7°, margin +15.9 dB, calculated
  - t21-4-42000-42500-fss-bss-gso grp 124725849 (10/10 groups exceed): pfd -110.3 vs limit -126.1 dB(W/m²) in 1000 kHz at δ 5.7°, margin +15.9 dB, calculated
  - t21-4-40500-42000-fss-bss-gso grp 124725849 (10/10 groups exceed): pfd -110.3 vs limit -119.3 dB(W/m²) in 1000 kHz at δ 5.7°, margin +9.1 dB, calculated
  - t21-4-40000-40500-fss-mss grp 124725865 (12/12 groups exceed): pfd -110.3 vs limit -114.7 dB(W/m²) in 1000 kHz at δ 5.7°, margin +4.4 dB, calculated
  - t21-4-47500-47900-fss-gso grp 124725877 (6/6 groups exceed): pfd -110.3 vs limit -114.7 dB(W/m²) in 1000 kHz at δ 5.7°, margin +4.4 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125545368 GRAVITAS (USA, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +14.9 dB.
  - t21-4-2200-2300-sr-so-eess-metsat grp 125752920 (1/1 groups exceed): pfd -129.1 vs limit -144.0 dB(W/m²) in 4 kHz at δ 90.0°, margin +14.9 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125545046 K-RADCUBE (KOR, API/A, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `screened_out`, max share —. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +13.8 dB.
  - t21-4-2200-2300-sr-so-eess-metsat grp 125630451 (5/5 groups exceed): pfd -130.2 vs limit -144.0 dB(W/m²) in 4 kHz at δ 67.0°, margin +13.8 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520174 PAZ_2-A (E, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +11.7 dB.
  - t21-4-5150-5216-fss grp 124741925 (4/4 groups exceed): pfd -152.3 vs limit -164.0 dB(W/m²) in 4 kHz at δ 90.0°, margin +11.7 dB, calculated
- Exceeds: cochannel:radiolocation (share 100%, p95 +16.7 dB); adjacent:radiolocation (share 100%, p95 +22.3 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520174 PAZ_2-A (E, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +11.7 dB.
  - t21-4-5150-5216-fss grp 324741925 (4/4 groups exceed): pfd -152.3 vs limit -164.0 dB(W/m²) in 4 kHz at δ 90.0°, margin +11.7 dB, calculated
- Exceeds: cochannel:radiolocation (share 100%, p95 +16.7 dB); adjacent:radiolocation (share 100%, p95 +22.0 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 322500245 INTELSAT7 66E (USA, Notification, GSO at 66°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 4%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +10.9 dB.
  - t21-4-10700-11700-fss-gso grp 295601284 (21/40 groups exceed): pfd -138.6 vs limit -149.5 dB(W/m²) in 4 kHz at δ 6.0°, margin +10.9 dB, calculated
  - t21-4-3400-4200-fss-gso grp 295600979 (15/109 groups exceed): pfd -148.9 vs limit -151.5 dB(W/m²) in 4 kHz at δ 6.0°, margin +2.6 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 95500027 INTELSAT7 66E (USA, Notification, GSO at 66°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 6%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +10.9 dB.
  - t21-4-10700-11700-fss-gso grp 95601284 (21/40 groups exceed): pfd -138.6 vs limit -149.5 dB(W/m²) in 4 kHz at δ 6.0°, margin +10.9 dB, calculated
  - t21-4-3400-4200-fss-gso grp 95600979 (15/109 groups exceed): pfd -148.9 vs limit -151.5 dB(W/m²) in 4 kHz at δ 6.0°, margin +2.6 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 123520029 USASAT-NGSO-3X (USA, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +10.1 dB.
  - t21-4-10700-11700-fss-ngso grp 123647115 (504/504 groups exceed): pfd -105.9 vs limit -116.0 dB(W/m²) in 1000 kHz at δ 90.0°, margin +10.1 dB, calculated
  - t21-4-11700-12500-fss-ngso grp 123647116 (336/342 groups exceed): pfd -105.9 vs limit -114.0 dB(W/m²) in 1000 kHz at δ 90.0°, margin +8.1 dB, calculated
  - t21-4-19300-19700-fss-bss-eess-iss-sr grp 123646264 (84/126 groups exceed): pfd -101.0 vs limit -105.0 dB(W/m²) in 1000 kHz at δ 90.0°, margin +4.0 dB, calculated
- Exceeds: cochannel:fixed (share 100%, p95 +20.3 dB); adjacent:fixed (share 78%, p95 +15.2 dB); cochannel:fss_es (share 100%, p95 +19.6 dB); adjacent:fss_es (share 100%, p95 +10.0 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 117520318 NSL-1 (ISR, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +8.8 dB.
  - t21-4-17700-19300-fss-ngso grp 117805664 (1/2 groups exceed): pfd -117.1 vs limit -125.9 dB(W/m²) in 1000 kHz at δ 5.0°, margin +8.8 dB, calculated
- Exceeds: cochannel:fss_es (share 100%, p95 +0.7 dB); adjacent:fss_es (share 33%, p95 +0.7 dB).
- Near limit: cochannel:fixed (share 0%, p95 -4.9 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520214 INSAT-COM(71E) (IND, CR/C, GSO at 71°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 12%. BR named FIN (A30A#7.1, A30A#7.1-CII).
- pfd vs Table 21-4: `exceeds`, max margin +8.7 dB.
  - t21-4-10700-11700-fss-gso grp 124727427 (20/20 groups exceed): pfd -141.3 vs limit -150.0 dB(W/m²) in 4 kHz at δ 5.0°, margin +8.7 dB, calculated
  - t21-4-17700-19300-fss-iss-gso grp 124727492 (214/312 groups exceed): pfd -111.3 vs limit -115.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +3.7 dB, calculated
  - t21-4-19300-19700-fss-bss-eess-iss-sr grp 124727502 (67/96 groups exceed): pfd -111.3 vs limit -115.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +3.7 dB, calculated
  - t21-4-3400-4200-fss-gso grp 124727416 (0/14 groups exceed): pfd -152.3 vs limit -152.0 dB(W/m²) in 4 kHz at δ 5.0°, margin -0.3 dB, calculated
- Near limit: cochannel:fss_es (share 0%, p95 -4.7 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126545148 ORACLE-M (USA, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `screened_out`, max share —. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +8.2 dB.
  - t21-4-8025-8500-eess-sr grp 126662554 (1/1 groups exceed): pfd -141.8 vs limit -150.0 dB(W/m²) in 4 kHz at δ 5.0°, margin +8.2 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520191 SAILSPACE-2-A-1 (CHN, CR/C, NGSO)

- Stations: worst `screened_out`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +7.5 dB.
  - t21-4-37500-40000-fss-mss-ngso grp 124813260 (2/2 groups exceed): pfd -112.5 vs limit -120.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +7.5 dB, calculated
  - t21-4-42000-42500-fss-bss-ngso grp 124813260 (2/2 groups exceed): pfd -112.5 vs limit -120.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +7.5 dB, calculated
  - t21-4-40000-40500-fss-mss grp 124813260 (2/2 groups exceed): pfd -102.1 vs limit -105.0 dB(W/m²) in 1000 kHz at δ 90.0°, margin +2.9 dB, calculated
  - t21-4-40500-42000-fss-bss-ngso grp 124813260 (2/2 groups exceed): pfd -102.1 vs limit -105.0 dB(W/m²) in 1000 kHz at δ 90.0°, margin +2.9 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520191 SAILSPACE-2-A-1 (CHN, CR/C, NGSO)

- Stations: worst `screened_out`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +7.5 dB.
  - t21-4-37500-40000-fss-mss-ngso grp 324813260 (2/2 groups exceed): pfd -112.5 vs limit -120.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +7.5 dB, calculated
  - t21-4-42000-42500-fss-bss-ngso grp 324813260 (2/2 groups exceed): pfd -112.5 vs limit -120.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +7.5 dB, calculated
  - t21-4-40000-40500-fss-mss grp 324813260 (2/2 groups exceed): pfd -102.1 vs limit -105.0 dB(W/m²) in 1000 kHz at δ 90.0°, margin +2.9 dB, calculated
  - t21-4-40500-42000-fss-bss-ngso grp 324813260 (2/2 groups exceed): pfd -102.1 vs limit -105.0 dB(W/m²) in 1000 kHz at δ 90.0°, margin +2.9 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520194 SECOMSAT-5-78E (E, CR/C, GSO at 78°E)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR named FIN (9.21/C).
- pfd vs Table 21-4: `exceeds`, max margin +7.0 dB.
  - t21-4-7250-7900-fss-metsat-mss-sr grp 124725292 (101/244 groups exceed): pfd -145.0 vs limit -152.0 dB(W/m²) in 4 kHz at δ 5.0°, margin +7.0 dB, calculated
- Exceeds: cochannel:mobile (share 100%, p95 +16.2 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520194 SECOMSAT-5-78E (E, CR/C, GSO at 78°E)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR named FIN (9.21/C).
- pfd vs Table 21-4: `exceeds`, max margin +7.0 dB.
  - t21-4-7250-7900-fss-metsat-mss-sr grp 324725292 (101/244 groups exceed): pfd -145.0 vs limit -152.0 dB(W/m²) in 4 kHz at δ 5.0°, margin +7.0 dB, calculated
- Exceeds: cochannel:mobile (share 100%, p95 +16.2 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125545390 USASAT-30-3 (USA, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +6.6 dB.
  - t21-4-25250-27500-fss-bss-eess-iss-sr grp 125743446 (1/1 groups exceed): pfd -98.4 vs limit -105.0 dB(W/m²) in 1000 kHz at δ 90.0°, margin +6.6 dB, calculated
  - t21-4-8025-8500-eess-sr grp 125743444 (1/1 groups exceed): pfd -140.0 vs limit -140.0 dB(W/m²) in 4 kHz at δ 90.0°, margin +0.0 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520183 CHINASAT-H-60.5E (CHN, CR/C, GSO at 60.5°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +6.6 dB.
  - t21-4-17700-19300-fss-iss-gso grp 324794008 (4/4 groups exceed): pfd -107.2 vs limit -113.8 dB(W/m²) in 1000 kHz at δ 7.4°, margin +6.6 dB, calculated
  - t21-4-19300-19700-fss-bss-eess-iss-sr grp 324794009 (2/2 groups exceed): pfd -107.2 vs limit -113.8 dB(W/m²) in 1000 kHz at δ 7.4°, margin +6.6 dB, calculated
  - t21-4-13400-13650-fss-gso grp 324794039 (4/5 groups exceed): pfd -151.8 vs limit -156.1 dB(W/m²) in 4 kHz at δ 7.4°, margin +4.3 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126500026 HTV-X-GN (J, Notification, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `meets`, max share 0%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +5.4 dB.
  - t21-4-2200-2300-sr-so-eess-metsat grp 126650615 (4/4 groups exceed): pfd -146.4 vs limit -151.8 dB(W/m²) in 4 kHz at δ 9.5°, margin +5.4 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125545392 MULA (PHL, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `meets`, max share 0%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +5.2 dB.
  - t21-4-2200-2300-sr-so-eess-metsat grp 125741809 (1/1 groups exceed): pfd -138.8 vs limit -144.0 dB(W/m²) in 4 kHz at δ 90.0°, margin +5.2 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520220 USASAT-NGSO-3Y-1 (USA, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +5.0 dB.
  - t21-4-40000-40500-fss-mss grp 124811692 (108/162 groups exceed): pfd -100.0 vs limit -105.0 dB(W/m²) in 1000 kHz at δ 90.0°, margin +5.0 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520220 USASAT-NGSO-3Y-1 (USA, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +5.0 dB.
  - t21-4-40000-40500-fss-mss grp 324811692 (108/162 groups exceed): pfd -100.0 vs limit -105.0 dB(W/m²) in 1000 kHz at δ 90.0°, margin +5.0 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520131 F-SAT-NG-15_B (F, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +4.9 dB.
  - t21-4-10700-11700-fss-ngso grp 124742043 (51/72 groups exceed): pfd -121.1 vs limit -126.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +4.9 dB, calculated
  - t21-4-11700-12500-fss-ngso grp 124742139 (51/72 groups exceed): pfd -119.1 vs limit -124.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +4.9 dB, calculated
  - t21-4-19300-19700-fss-bss-eess-iss-sr grp 124742632 (36/72 groups exceed): pfd -110.1 vs limit -115.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +4.9 dB, calculated
  - t21-4-40000-40500-fss-mss grp 124743592 (108/216 groups exceed): pfd -110.1 vs limit -115.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +4.9 dB, calculated
- Exceeds: cochannel:fixed (share 80%, p95 +15.6 dB); cochannel:fss_es (share 100%, p95 +8.2 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520131 F-SAT-NG-15_B (F, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +4.9 dB.
  - t21-4-10700-11700-fss-ngso grp 324742043 (51/72 groups exceed): pfd -121.1 vs limit -126.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +4.9 dB, calculated
  - t21-4-11700-12500-fss-ngso grp 324742139 (51/72 groups exceed): pfd -119.1 vs limit -124.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +4.9 dB, calculated
  - t21-4-19300-19700-fss-bss-eess-iss-sr grp 324742632 (36/72 groups exceed): pfd -110.1 vs limit -115.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +4.9 dB, calculated
  - t21-4-40000-40500-fss-mss grp 324743592 (108/216 groups exceed): pfd -110.1 vs limit -115.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +4.9 dB, calculated
- Exceeds: cochannel:fixed (share 67%, p95 +12.3 dB); cochannel:fss_es (share 100%, p95 +11.9 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520184 CHINASAT-G-33.5E (CHN, CR/C, GSO at 33.5°E)

- Stations: worst `exceeds`, max share violating 17%. Generic: worst `exceeds`, max share 100%. BR named FIN (9.14).
- pfd vs Table 21-4: `exceeds`, max margin +4.6 dB.
  - t21-4-17700-19300-fss-iss-gso grp 324793617 (4/4 groups exceed): pfd -107.1 vs limit -111.8 dB(W/m²) in 1000 kHz at δ 11.4°, margin +4.6 dB, calculated
  - t21-4-19300-19700-fss-bss-eess-iss-sr grp 324793618 (2/2 groups exceed): pfd -107.1 vs limit -111.8 dB(W/m²) in 1000 kHz at δ 11.4°, margin +4.6 dB, calculated
  - t21-4-13400-13650-fss-gso grp 324793950 (8/9 groups exceed): pfd -150.1 vs limit -154.4 dB(W/m²) in 4 kHz at δ 11.4°, margin +4.3 dB, calculated
- Exceeds: cochannel:fss_es (share 17%, p95 +16.6 dB).
- Main beam: station:616738:305 (fss_es, 18737.500–18792.500 MHz, az 176.1°, 45 dBi): satellite at az 176.2°, el 18.3°, off-axis 0.1° of θ3dB 1.0°.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125520053 USASAT-NGSO-8F (USA, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 67%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +4.3 dB.
  - t21-4-19300-19700-fss-bss-eess-iss-sr grp 125805371 (256/256 groups exceed): pfd -100.7 vs limit -105.0 dB(W/m²) in 1000 kHz at δ 90.0°, margin +4.3 dB, calculated
  - t21-4-40000-40500-fss-mss grp 125806023 (18/18 groups exceed): pfd -104.9 vs limit -105.0 dB(W/m²) in 1000 kHz at δ 90.0°, margin +0.1 dB, calculated
- Exceeds: cochannel:fss_es (share 67%, p95 +6.0 dB).
- Near limit: adjacent:fixed (share 0%, p95 -0.6 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520214 INSAT-COM(71E) (IND, CR/C, GSO at 71°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 19%. BR named FIN (A30A#7.1, A30A#7.1-CII).
- pfd vs Table 21-4: `exceeds`, max margin +3.7 dB.
  - t21-4-17700-19300-fss-iss-gso grp 324727502 (67/96 groups exceed): pfd -111.3 vs limit -115.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +3.7 dB, calculated
  - t21-4-19300-19700-fss-bss-eess-iss-sr grp 324727502 (67/96 groups exceed): pfd -111.3 vs limit -115.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +3.7 dB, calculated
- Near limit: cochannel:fss_es (share 0%, p95 -3.2 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125500068 INSAT-KA68ER (IND, Notification, GSO at 68°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 11%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +3.5 dB.
  - t21-4-17700-19300-fss-iss-gso grp 125622933 (169/222 groups exceed): pfd -111.3 vs limit -114.8 dB(W/m²) in 1000 kHz at δ 5.4°, margin +3.5 dB, calculated
  - t21-4-19300-19700-fss-bss-eess-iss-sr grp 125622943 (55/72 groups exceed): pfd -111.3 vs limit -114.8 dB(W/m²) in 1000 kHz at δ 5.4°, margin +3.5 dB, calculated
  - t21-4-3400-4200-fss-gso grp 125623305 (0/6 groups exceed): pfd -152.3 vs limit -151.8 dB(W/m²) in 4 kHz at δ 5.4°, margin -0.6 dB, calculated
- Near limit: cochannel:fss_es (share 0%, p95 -5.7 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126545098 SNAPPY (USA, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `meets`, max share 0%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +3.2 dB.
  - t21-4-2200-2300-sr-so-eess-metsat grp 126662059 (1/1 groups exceed): pfd -140.8 vs limit -144.0 dB(W/m²) in 4 kHz at δ 90.0°, margin +3.2 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 103500417 COMPASS-80E (CHN, Notification, GSO at 80°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +3.2 dB.
  - t21-4-3400-4200-fss-gso grp 109692106 (1/5 groups exceed): pfd -148.8 vs limit -152.0 dB(W/m²) in 4 kHz at δ 5.0°, margin +3.2 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 303500417 COMPASS-80E (CHN, Notification, GSO at 80°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +3.2 dB.
  - t21-4-3400-4200-fss-gso grp 309692106 (1/5 groups exceed): pfd -148.8 vs limit -152.0 dB(W/m²) in 4 kHz at δ 5.0°, margin +3.2 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125520047 USASAT-NGSO-8E (USA, CR/C, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +2.7 dB.
  - t21-4-19300-19700-fss-bss-eess-iss-sr grp 125803531 (110/256 groups exceed): pfd -112.3 vs limit -115.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin +2.7 dB, calculated
  - t21-4-40000-40500-fss-mss grp 125804183 (0/18 groups exceed): pfd -116.5 vs limit -115.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin -1.5 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126500052 PYXIS (J, Notification, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `meets`, max share 0%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +2.1 dB.
  - t21-4-8025-8500-eess-sr grp 126634699 (1/1 groups exceed): pfd -137.9 vs limit -140.0 dB(W/m²) in 4 kHz at δ 90.0°, margin +2.1 dB, calculated
  - t21-4-2200-2300-sr-so-eess-metsat grp 126634698 (1/1 groups exceed): pfd -142.1 vs limit -144.0 dB(W/m²) in 4 kHz at δ 90.0°, margin +1.9 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126545131 ION SCV-025 (I, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `meets`, max share 0%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +2.1 dB.
  - t21-4-2200-2300-sr-so-eess-metsat grp 126656468 (1/1 groups exceed): pfd -141.9 vs limit -144.0 dB(W/m²) in 4 kHz at δ 90.0°, margin +2.1 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126545132 ION SCV-026 (I, API/A, NGSO)

- Stations: worst `screened_out`, max share violating —. Generic: worst `meets`, max share 0%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +2.1 dB.
  - t21-4-2200-2300-sr-so-eess-metsat grp 126664731 (1/1 groups exceed): pfd -141.9 vs limit -144.0 dB(W/m²) in 4 kHz at δ 90.0°, margin +2.1 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 119500051 COMPASS-80.3E (CHN, Notification, GSO at 80.3°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +1.6 dB.
  - t21-4-3400-4200-fss-gso grp 120711232 (3/5 groups exceed): pfd -150.4 vs limit -152.0 dB(W/m²) in 4 kHz at δ 5.0°, margin +1.6 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 319500051 COMPASS-80.3E (CHN, Notification, GSO at 80.3°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +1.6 dB.
  - t21-4-3400-4200-fss-gso grp 320711232 (3/5 groups exceed): pfd -150.4 vs limit -152.0 dB(W/m²) in 4 kHz at δ 5.0°, margin +1.6 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126545060 AE4LA (J, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `meets`, max share 0%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +0.9 dB.
  - t21-4-2200-2300-sr-so-eess-metsat grp 126633252 (2/2 groups exceed): pfd -143.1 vs limit -144.0 dB(W/m²) in 4 kHz at δ 90.0°, margin +0.9 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126545119 SOLAR SENTRY (D, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 8%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +0.3 dB.
  - t21-4-2200-2300-sr-so-eess-metsat grp 126664723 (1/2 groups exceed): pfd -143.7 vs limit -144.0 dB(W/m²) in 4 kHz at δ 90.0°, margin +0.3 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125500277 GW-S (CHN, Notification, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `exceeds`, max margin +0.2 dB.
  - t21-4-7250-7900-fss-metsat-mss-sr grp 125867341 (1/4 groups exceed): pfd -151.8 vs limit -152.0 dB(W/m²) in 4 kHz at δ 5.0°, margin +0.2 dB, calculated
  - t21-4-10700-11700-fss-ngso grp 125867346 (0/6 groups exceed): pfd -126.4 vs limit -126.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin -0.4 dB, calculated
  - t21-4-11700-12500-fss-ngso grp 125867361 (0/9 groups exceed): pfd -126.4 vs limit -124.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin -2.4 dB, calculated
  - t21-4-40000-40500-fss-mss grp 125867357 (0/1 groups exceed): pfd -117.4 vs limit -115.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin -2.4 dB, calculated
- Exceeds: cochannel:fixed (share 18%, p95 +2.7 dB); cochannel:mobile (share 100%, p95 +39.1 dB); adjacent:mobile (share 100%, p95 +33.2 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:


## A. Stations source: a criterion is exceeded

### 125520111 STARERA-3 (CHN, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR named FIN (9.14).
- pfd vs Table 21-4: `meets`, max margin -4.4 dB.
- Exceeds: adjacent:mobile (share 100%, p95 +57.1 dB).
- Near limit: cochannel:fss_es (share 0%, p95 -4.8 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125545396 GY-2 (CHN, API/A, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -7.4 dB.
- Exceeds: cochannel:radiolocation (share 100%, p95 +33.0 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 117520372 AST-NG-C-4 (F, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -15.3 dB.
- Exceeds: cochannel:mobile (share 100%, p95 +30.6 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126500107 CONNECTA IOT (TUR, Notification, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -0.1 dB.
  - t21-4-2200-2300-sr-so-eess-metsat grp 126662090 (0/2 groups exceed): pfd -144.1 vs limit -144.0 dB(W/m²) in 4 kHz at δ 90.0°, margin -0.1 dB, calculated
- Exceeds: cochannel:mobile (share 100%, p95 +29.9 dB).
- Near limit: cochannel:fixed (share 0%, p95 -5.0 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 323520029 USASAT-NGSO-3X (USA, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_assessed`, max margin —.
- Exceeds: cochannel:fixed (share 100%, p95 +20.3 dB); adjacent:fixed (share 40%, p95 +15.1 dB); cochannel:fss_es (share 100%, p95 +19.2 dB); adjacent:fss_es (share 100%, p95 +7.3 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520173 QATARGOV-G1-25.5E (QAT, CR/C, GSO at 25.5°E)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR named FIN (9.21/C).
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Exceeds: cochannel:mobile (share 100%, p95 +14.0 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520173 QATARGOV-G1-25.5E (QAT, CR/C, GSO at 25.5°E)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR named FIN (9.21/C).
- pfd vs Table 21-4: `meets`, max margin -8.8 dB.
- Exceeds: cochannel:mobile (share 100%, p95 +14.0 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 317520372 AST-NG-C-4 (F, CR/C, NGSO)

- Stations: worst `exceeds`, max share violating 100%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -15.3 dB.
- Exceeds: cochannel:mobile (share 100%, p95 +4.4 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:


## C. Stations source: within 6 dB of a criterion (near limit)

### 125545393 EUHT (CHN, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Near limit: adjacent:mobile (share 0%, p95 -5.2 dB).
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:


## D. Generic population only: a criterion is exceeded

### 324520204 KAZSAT-KA-67.2E-2 (KAZ, CR/C, GSO at 67.2°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 18%. BR did not name FIN.
- pfd vs Table 21-4: `not_assessed`, max margin -0.4 dB.
  - t21-4-17700-19300-fss-iss-gso grp 324725956 (0/9 groups exceed): pfd -115.1 vs limit -114.7 dB(W/m²) in 1000 kHz at δ 5.7°, margin -0.4 dB, calculated
  - t21-4-19300-19700-fss-bss-eess-iss-sr grp 324725956 (0/9 groups exceed): pfd -115.1 vs limit -114.7 dB(W/m²) in 1000 kHz at δ 5.7°, margin -0.4 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 317520318 NSL-1 (ISR, CR/C, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 7%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -8.2 dB.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126545069 GD-B (CHN, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -0.5 dB.
  - t21-4-8025-8500-eess-sr grp 126656492 (0/4 groups exceed): pfd -140.5 vs limit -140.0 dB(W/m²) in 4 kHz at δ 90.0°, margin -0.5 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126545127 K-COMSAT (KOR, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -4.0 dB.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126545114 PUXING-1 (CHN, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 0%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -6.2 dB.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 103500416 COMPASS-58.75E (CHN, Notification, GSO at 58.75°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -2.1 dB.
  - t21-4-3400-4200-fss-gso grp 109671614 (0/5 groups exceed): pfd -152.7 vs limit -150.6 dB(W/m²) in 4 kHz at δ 7.8°, margin -2.1 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 303500416 COMPASS-58.75E (CHN, Notification, GSO at 58.75°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -2.1 dB.
  - t21-4-3400-4200-fss-gso grp 309671614 (0/5 groups exceed): pfd -152.7 vs limit -150.6 dB(W/m²) in 4 kHz at δ 7.8°, margin -2.1 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125512022 RGS-S-45E (RUS, Notification, GSO at 45°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -2.6 dB.
  - t21-4-3400-4200-fss-gso grp 125622408 (0/6 groups exceed): pfd -151.8 vs limit -149.3 dB(W/m²) in 4 kHz at δ 10.5°, margin -2.6 dB, calculated
  - t21-4-7250-7900-fss-metsat-mss-sr grp 125622435 (0/17 groups exceed): pfd -151.8 vs limit -149.3 dB(W/m²) in 4 kHz at δ 10.5°, margin -2.6 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125512023 RGS-S-35E (RUS, Notification, GSO at 35°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -3.0 dB.
  - t21-4-3400-4200-fss-gso grp 125622496 (0/6 groups exceed): pfd -151.8 vs limit -148.8 dB(W/m²) in 4 kHz at δ 11.4°, margin -3.0 dB, calculated
  - t21-4-7250-7900-fss-metsat-mss-sr grp 125622523 (0/17 groups exceed): pfd -151.8 vs limit -148.8 dB(W/m²) in 4 kHz at δ 11.4°, margin -3.0 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520193 MTG-EUM_9.5E (D, CR/C, GSO at 9.5°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -1.4 dB.
  - t21-4-25250-27500-fss-bss-eess-iss-sr grp 124725812 (0/2 groups exceed): pfd -113.7 vs limit -112.3 dB(W/m²) in 1000 kHz at δ 10.4°, margin -1.4 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520192 MTG-EUM_3.5E (D, CR/C, GSO at 3.5°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -0.9 dB.
  - t21-4-25250-27500-fss-bss-eess-iss-sr grp 124725805 (0/2 groups exceed): pfd -113.7 vs limit -112.7 dB(W/m²) in 1000 kHz at δ 9.6°, margin -0.9 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 309500876 CHINASAT-31 (CHN, Notification, GSO at 80°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 1%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -3.7 dB.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 109500876 CHINASAT-31 (CHN, Notification, GSO at 80°E)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 0%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -3.7 dB.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 119545232 TYSAR-01 (CHN, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -16.9 dB.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 123520028 USASAT-NGSO-12 (USA, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520182 CENTISPACE-5 (CHN, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520187 INSAT-NAV-NGSO4 (IND, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520188 KPS-NGSO-A (KOR, CR/C, NGSO)

- Stations: worst `screened_out`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -0.8 dB.
  - t21-4-10700-12500-fss-ngso-heo grp 124793159 (0/24 groups exceed): pfd -129.8 vs limit -129.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin -0.8 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520199 ONDOSAT (MNG, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 37%. BR did not name FIN.
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520203 LUMIRX-1 (KOR, CR/C, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_assessed`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520211 METEOR-3M (RUS, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 124520221 NUSANTARA-NGSO-PS1 (INS, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125512024 RGS-N (RUS, Notification, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125545395 INSIGHT-A (CHN, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -5.2 dB.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 125545403 CITYSEC (CHN, API/A, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 87%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -11.1 dB.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 126500063 USASAT-NGSO-12 (USA, Notification, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 323520028 USASAT-NGSO-12 (USA, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520182 CENTISPACE-5 (CHN, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520187 INSAT-NAV-NGSO4 (IND, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520188 KPS-NGSO-A (KOR, CR/C, NGSO)

- Stations: worst `screened_out`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `meets`, max margin -0.8 dB.
  - t21-4-10700-12500-fss-ngso-heo grp 324793159 (0/24 groups exceed): pfd -129.8 vs limit -129.0 dB(W/m²) in 1000 kHz at δ 5.0°, margin -0.8 dB, calculated
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520192 MTG-EUM_3.5E (D, CR/C, GSO at 3.5°E)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520193 MTG-EUM_9.5E (D, CR/C, GSO at 9.5°E)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520203 LUMIRX-1 (KOR, CR/C, NGSO)

- Stations: worst `meets`, max share violating 0%. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_assessed`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520211 METEOR-3M (RUS, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:

### 324520221 NUSANTARA-NGSO-PS1 (INS, CR/C, NGSO)

- Stations: worst `not_applicable`, max share violating —. Generic: worst `exceeds`, max share 100%. BR did not name FIN.
- pfd vs Table 21-4: `not_applicable`, max margin —.
- Reviewer verdict: ☐ concern ☐ no concern ☐ unsure — note:
