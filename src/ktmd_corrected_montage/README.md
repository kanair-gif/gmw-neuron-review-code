# KTMD corrected-montage macaque analysis

This directory contains the corrected-montage macaque ECoG analysis code bundle
used for the manuscript-facing KTMD/NeuroTycho analyses.

Main bundle:

```text
KTMD_ANALYSIS_CODE_COMPLETE_20260819/
```

Important entry points:

| File | Purpose |
| --- | --- |
| `pipeline/run_full_corrected_pipeline.py` | Full corrected-montage pipeline. |
| `pipeline/run_ktmd_state_v2.py` | Day/state-specific operator and signature estimation. |
| `pipeline/run_cross_day.py` | Cross-day and leave-one-day-out analyses. |
| `pipeline/fast_wmi.py` | WMI and related mediation metric calculations. |
| `pipeline/build_corrected_montages.py` | Official-map constrained local bipolar montage construction. |
| `pipeline/strict_postrun_verifier.py` | Post-run completion and provenance checks. |
| `figure_generation/regenerate_recovery_consistent_figures.py` | Recovery-consistent figure regeneration. |

The full pipeline requires external NeuroTycho raw archives or split archive
parts. Expected raw archive metadata are in:

```text
KTMD_ANALYSIS_CODE_COMPLETE_20260819/pipeline/expected_master_index.json
```

No raw ECoG archive body is bundled in this public reviewer-code repository.

