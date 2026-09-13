# 100K → 1M Investment Governance — V4.1

## Decision Log / Historical Governance Snapshot

V4.1 is an additive storage upgrade focused on auditability. It preserves the existing `data/investment_journal.db` and existing decision rows.

### Core principle

**Decision Log is a Snapshot, not Live Data.**

A historical decision must remain the same even when today's market data, indicators, scores, or governance engine change.

### What changed

- Existing `decisions` table is preserved.
- Missing V4.1 columns are added with SQLite `ALTER TABLE`.
- Existing JSON audit payloads stored in `notes` are backfilled into `snapshot_json` and queryable relational fields.
- Non-JSON legacy notes are preserved; the migration does not invent missing historical evidence.
- New decisions automatically freeze the V4 governance payload into `snapshot_json`.
- `governance_version` records the engine version used for the stored snapshot.
- `data_as_of` is kept separate from `created_at` for future market-data timestamp integration.

### V4.1 fields

`decision_id` is the existing SQLite `id`.

- Identity: `id`, `created_at`, `ticker`
- Market: `current_price`
- Research: `research_score`, `evidence_coverage`
- Risk: `risk_score`
- Early Warning: `early_warning_status`
- Regime: `short_term_regime`, `long_term_regime`
- Risk/Reward: `entry_price`, `stop_loss`, `target_price`, `risk_reward`, `rr_threshold`, `rr_pass`
- Governance: `process_status`, `thesis_status`
- Decision: `decision`, `decision_reason`
- Audit: `governance_version`, `data_as_of`, `snapshot_json`
- Analyst notes: existing `notes`

### Backward compatibility

The current V4 `app_us_research.py` can continue calling `save_decision(...)` with its existing arguments. V4.1 storage parses the existing audit JSON format and fills the new fields automatically.

### Important boundary

V4.1 does **not** add outcome tracking yet. The lifecycle remains:

`Decision → Time Passes → Outcome → Review`

Outcome and review belong to a future governance iteration.
