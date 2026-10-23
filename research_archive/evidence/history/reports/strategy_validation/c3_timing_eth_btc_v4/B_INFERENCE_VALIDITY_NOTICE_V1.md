> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Stage1 B inference validity notice — V1

Status: `INFERENCE_INCOMPLETE`; this notice qualifies the saved B Stage1 V3 training artifact. It does not modify or replace any original report, event CSV, cost-cell ledger, attempt record, or approved lock. No numeric source partition was reread and no rerun was performed.

## Finding

The V6 protocol says a control that cannot be drawn remains unmatched and retains the sample-floor failure. In the saved run, candidate event-control contrasts were first reduced to events with all 100 replicate controls (`n_controls == 100`). The sample-floor helper then evaluated only that complete-pair subset. This produced `sample_eligible=true` even though each candidate had unmatched control rows. Consequently, the stored Holm values and simultaneous lower bounds summarize only the complete-pair subset and are **not valid primary pass/fail inference** under the preregistration. Interpret the primary inference for every candidate as `INFERENCE_INCOMPLETE`.

The separate full-sample ETH-only and hedged-pair ledgers were constructed from all labeled natural candidate events, without filtering on matched-control completeness. Their net account returns and yearly fresh-cash returns remain descriptive outputs of the saved run and are unaffected by this inference validity issue. The 5+5bp costed BTC/Core4 account comparisons are also retained as full-sample descriptive account outputs. They do not repair the incomplete primary matched-control inference.

## Candidate control completeness and invalid subset diagnostics

The numeric p-values and bounds below are copied from the original candidate evidence file only to identify the affected outputs. They are subset diagnostics; do not interpret them as valid Holm tests or valid Bonferroni lower bounds.

| Candidate | Natural events | Events with 100 controls | Unmatched schedule rows | Replicates | Complete account replicates | Saved Holm p, invalid subset diagnostic | Saved 98.75% lower, invalid subset diagnostic |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| lead_4h | 383 | 378 | 500 | 100 | 0 | 0.149585 | -0.00039588 |
| lead_24h | 223 | 220 | 300 | 100 | 0 | 1.000000 | -0.00516999 |
| lag_4h | 385 | 380 | 500 | 100 | 0 | 1.000000 | -0.00305443 |
| lag_24h | 239 | 236 | 300 | 100 | 0 | 1.000000 | -0.00586853 |

All four candidates therefore fail the matched-control completeness gate. The corrected interpretation is `NO_SELECTION`; this notice does not establish that the true candidate effects are negative or positive. The full-sample account return evidence remains descriptive only, and the no-trade verdict is unchanged.

## Provenance

- Original training report SHA256: `a02f441d3d3abbc76556a8a473358fc68132267d5c6d69eafd12c55db51b05ca`
- Original approved lock SHA256: `b0fcad40da822c8a5446afdd9583f7f01c14f2cd640ea2d869a18a76e9bcc2d0`
- Original completed attempt SHA256: `69680a9016a654d0c13304334a2a066f8ad6c51a1ac885311848ff5635c469e6`
- Original event CSV and schedule CSV hashes are embedded in the JSON report manifest. This notice was built from those saved artifacts only.
- The required V4 correction is to retain unmatched events in sample-floor eligibility, mark the primary inference `INFERENCE_INCOMPLETE`, expose no valid Holm p/lower bound for candidate selection, and fail selection closed. A synthetic test for one unmatched control is required. V4 remains pending review; no real numeric run is authorized by this notice.
