# Macaque Blockwise Phase Recheck

Date: 2026-08-27

## Question

Ryota was concerned whether the KTMD macaque blockwise "time-series" display is appropriate relative to the original raw data phase structure, and whether a figure with visible gaps between phases can be recreated.

## Sources Checked

- Raw NeuroTycho / KTMD ZIP symlink view: `data/raw/ktmd_neurotycho/*.zip`
- Raw metadata read inside each ZIP without unpacking or modifying raw files:
  - `Info-*.txt`
  - `Session*/Condition.mat`
  - `Session*/ECoGTime.mat`
- Result table checked:
  - `_incoming/from_local_not_organized/GMW19_ECoG_CorrectedMontage_Manuscript_Handoff_20260817_v2.zip::GMW19_ECoG_CorrectedMontage_Manuscript_Handoff_20260817_v2/02_FINAL_TABLES/updated_lodo_blockwise_trajectories_recovery_consistent.csv`
- Figure regeneration logic inspected:
  - `_incoming/kanai_manual_transfer/various_data/KTMD_ANALYSIS_CODE_COMPLETE_20260819.zip::KTMD_ANALYSIS_CODE_COMPLETE_20260819/figure_generation/regenerate_recovery_consistent_figures.py`

## What Was Verified

Each unique `(animal, date, state, block, session, start_s, end_s)` window in the recovery-consistent blockwise table was mapped back to the corresponding raw `Condition.mat` event interval:

| Result state | Raw condition labels |
| --- | --- |
| `eyes_open` | `AwakeEyesOpened-Start` to `AwakeEyesOpened-End` |
| `eyes_closed` | `AwakeEyesClosed-Start` to `AwakeEyesClosed-End` |
| `deep_anesthesia` | `Anesthetized-Start` to `Anesthetized-End` |
| `recovery_eyes_closed` | `RecoveryEyesClosed-Start` to `RecoveryEyesClosed-End` |
| `recovery_eyes_open` | `RecoveryEyesOpened-Start` to `RecoveryEyesOpened-End` |

Checks performed:

- Result-table session number matches the raw session containing the phase label.
- Result-table `start_s` and `end_s` are inside the raw condition interval.
- Every block window is positive-duration and 80 seconds long.
- Blocks are monotonic and non-overlapping within each phase.
- Each checked condition contributes blocks 1-6.

## Result

All checked block windows passed.

| Check | Result |
| --- | --- |
| Unique block windows checked | 306 |
| Conditions checked | 51 |
| Status counts | 306 `ok`, 0 mismatch |
| Window duration | all 80.0 s |
| Minimum margin from raw phase start | 29.995 s |
| Minimum margin before raw phase end | 29.995 s |
| Animals represented | Chibi, George, Kin2, Su |
| Recovery states in recovery-consistent table | George, Kin2, Su only |
| Post-check raw ZIP hash revalidation | 11 checked, 0 errors against `KTMD_NEUROTYCHO_RAW_ARCHIVE_MANIFEST_2026-08-25.csv` |

Detailed machine-readable outputs:

- `docs/audit/MACAQUE_BLOCKWISE_RAW_PHASE_RECHECK_2026-08-27.csv`
- `docs/audit/MACAQUE_BLOCKWISE_RAW_PHASE_RECHECK_2026-08-27.json`

## Raw Phase Structure

The raw metadata explicitly supports the chronological phase order used by the analysis: awake eyes-open, awake eyes-closed, deep anesthesia, recovery eyes-closed, recovery eyes-open. In the raw files this order is stored as named condition events, not merely inferred from filenames.

Notable session patterns:

- George 20110112, 20110113, 20110114: awake and anesthetized intervals are in Session 1; recovery intervals are in Session 2.
- Kin2 20110513 and 20110524; Su 20110523, 20110526, 20110527; Chibi 20110622: awake, anesthetized, and recovery are separated across Session 1, Session 2, and Session 3.
- Kin2 20110525: awake eyes-open is Session 1, awake eyes-closed is Session 2, anesthetized is Session 3, and recovery is Session 4.
- Chibi 20110621 has no recovery session in the raw metadata and contributes only awake/deep states in the checked recovery-consistent table.
- Chibi 20110622 has raw recovery metadata, but recovery rows are excluded from the checked recovery-consistent blockwise table, consistent with the v2 recovery audit note.

## Figure Created

A phase-gapped blockwise figure was regenerated from the recovery-consistent row-level LODO table.

Outputs:

- `figures/final/ktmd_blockwise_trajectories_recovery_consistent_awake_mean_one_gapped_2026-08-27.svg`
- `figures/final/ktmd_blockwise_trajectories_recovery_consistent_awake_mean_one_gapped_2026-08-27.png`
- `docs/audit/MACAQUE_BLOCKWISE_GAPPED_FIGURE_SOURCE_2026-08-27.csv`
- `docs/audit/MACAQUE_BLOCKWISE_GAPPED_FIGURE_SOURCE_2026-08-27.json`

After user review, a narrower half-gap version was generated and inserted into the Neuron V22 controlled working copy:

- `figures/final/ktmd_blockwise_trajectories_recovery_consistent_awake_mean_one_gapped_halfgap_2026-08-27.svg`
- `figures/final/ktmd_blockwise_trajectories_recovery_consistent_awake_mean_one_gapped_halfgap_2026-08-27.png`
- `docs/audit/MACAQUE_BLOCKWISE_GAPPED_HALFGAP_FIGURE_SOURCE_2026-08-27.csv`
- `docs/audit/MACAQUE_BLOCKWISE_GAPPED_HALFGAP_FIGURE_SOURCE_2026-08-27.json`
- Neuron V22 active Figure 6 source: `manuscript/submission/neuron_v22_candidate/working_copy/release_zip/GMW_Neuron_V22_release_dir/figures_source/figures_macaque_corrected/figure_updated_blockwise_trajectories_RECOVERY_CONSISTENT_awake_mean_one_GAPPED_HALFGAP_20260827.png`

The figure intentionally:

- draws blocks 1-6 within each phase;
- stops lines at every phase boundary;
- inserts blank x-axis gaps between phases;
- labels recovery panels as n=3 because only George/Kin2/Su are used for recovery in the recovery-consistent source table;
- treats inter-phase gaps as categorical visual gaps, not elapsed-time scaling.

## Important Caution

Do not use `updated_blockwise_trajectories_awake_mean_one_by_animal.csv` as the recovery-consistent source for this specific phase-gapped figure without further review. It still contains Chibi recovery rows, whereas the recovery-consistent row-level table excludes Chibi recovery. For the 2026-08-27 regenerated gapped figure, normalization was recomputed from `updated_lodo_blockwise_trajectories_recovery_consistent.csv`.

## Interpretation

The phase labels and phase boundaries used by the blockwise table are supported by the raw `Condition.mat` metadata. Therefore, the within-phase blockwise progression itself appears appropriate at the raw-metadata level.

However, the display should not imply continuous elapsed time across phase boundaries. The safer presentation for a "time-series-like" blockwise plot is the phase-gapped version, where each phase has its own six ordered blocks and line segments are visually interrupted between phases.

## Not Verified Here

- The full spectral / corrected-montage pipeline was not rerun from raw ECoG samples.
- Numerical metric values were not recomputed from raw voltage traces in this pass.
- The check verifies raw phase/event alignment for the existing recovery-consistent result table.
