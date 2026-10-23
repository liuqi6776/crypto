> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Archive — legacy perpetual research (read-only reference)

`legacy_leverage_research/` holds a copy of the source repository's
perpetual/leverage research and its supporting documents. It is a **record**, not
an endorsement.

## Contents

| Path | What |
| :--- | :--- |
| `legacy_leverage_research/scripts/` | 71 Python files from `<SOURCE_ROOT:crypto-source>/leverage_research/*.py` |
| `legacy_leverage_research/charts/` | 53 PNG/npz/CSV outputs from `leverage_research/charts/` |
| `legacy_leverage_research/summary_data/` | 21 CSV summary tables (module root + `summary_data/`) |
| `legacy_leverage_research/trade_logs/` | 25 per-portfolio trade CSVs |
| `legacy_leverage_research/docs/` | 23 documents: `README.md`, `WALKTHROUGH_LEVERAGE.md`, `DATA_DICTIONARY.md`, and the source repo's framework / preregistration / audit / protocol documents |
| `legacy_leverage_research/repo_meta/AGENTS.md` | source repository research-integrity rules |
| `catalog/dataset_registry.json` | verified vs excluded source datasets |
| `inventory/` | manifests, per-file provenance, SHA256 digests, generated reports |

Original filenames are preserved. `archive/inventory/copy_provenance.json` maps
every archived file back to its absolute source path.

## Status of the numbers inside

> **`LEGACY_RESEARCH` — do not present as tradable results.**

`legacy_leverage_research/docs/README.md` quotes headline figures (funding-arb
CAGR/Sharpe, "zero liquidations", hybrid total return). The source repository's
own audits — `docs/CLAIM_CONSISTENCY_AUDIT.md` and `docs/v1_gate_status.json`,
both archived here — state that these results do not satisfy the frozen
v1 admission gate (`docs/CRYPTO_QUANT_FRAMEWORK_V1.md`): funding, margin paths,
participation limits and cost stress were not satisfied as a single ledger.

They are archived for reference and porting only.

## What was excluded, and why

| Excluded | Reason |
| :--- | :--- |
| `leverage_research/__pycache__/` | compiled bytecode; transient |
| `.env`, credentials, secrets | safety |
| spot-only material (`data/spot`, `data/pit_spot`, `history/spot_5m`) | out of scope for a perpetual-only project |
| repo-root `{SYM}_4h_2020_2026.parquet` | ambiguous/mixed market type per `crypto_quant/data/catalog.py` |
| repo-root `{SYM}_1h/1d_*.parquet` | unverified provenance |
| `paper_logs/`, `paper_state/`, `checkpoints/`, `predictions/` | transient process state / model binaries |
| `server/`, `scripts/`, `crypto_quant/`, `strategies/`, `tests/` (source) | unrelated to a standalone Freqtrade project |
| multi-MB interactive HTML dashboards | not perpetual-specific evidence; size |

## Regenerating the archive

```powershell
python scripts\copy_legacy_archive.py --dry-run   # preview
python scripts\copy_legacy_archive.py             # copy (idempotent)
python scripts\build_inventory.py                 # re-hash + refresh provenance
```

The source repository and the D: drive are read-only; the copier never writes to
them.
