# Space pfd vs RR Table 21-4 delivered

The pfd check `art21-1` is implemented end to end. `data/ref/rr21_pfd_limits.json` now holds 52 Table 21-4 rows for
Region 1, transcribed from the RR 2024 PDF downloaded from itu.int, with 8 entries excluded and a separately typed
cross-check test for every encoded row. `riia/pfd.py` computes the worst pfd over Finland per row, and the result
reaches the API, the `/risk` column, filter and notice sheet, the review report, the CSV and the chat context. The
service match uses `srv_cls` station classes, verified against BR Preface Table 3.

The first 3074 run gave an implausible +122.5 dB margin, which was traced to `pwr_ds_max = +73` dB(W/Hz), a sign
error. 91 emissions in 3074 hold more power in their averaging band than in the whole carrier; the check now treats
them as data errors. The code review found that a notified `c_pfd` was rescaled flat over its own bandwidth rather
than over the carrier, which could hide an exceedance for a narrow carrier; that is fixed and tested.

On 3074, 47 notices exceed and 31 are near a limit. All 108 exceeding checks rest on peak gain toward Finland, and a
10 dB off-beam gain clears 31 of the 47. All 4,508 Monte Carlo hazards are unchanged from before.

Open: a person must sign off the transcription. TT&C-only groups (ED/EK/ER) match only the space operation rows. The
dev DB still holds pre-pfd results until 3074 is re-assessed.
