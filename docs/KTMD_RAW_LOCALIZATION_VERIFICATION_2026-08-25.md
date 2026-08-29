# KTMD Raw Localization Verification

Date: 2026-08-25 Asia/Tokyo

Recheck: after the user reported adding the local KTMD folder contents under
`_incoming/kanai_manual_transfer/KTMD/`, the same directory was re-read and all
raw ZIP archive hashes were recomputed on 2026-08-25. The recheck found 11
expected raw archives, 0 missing expected archives, 0 extra raw archives, and 0
comparison errors.

## Scope

This note verifies the KTMD / NeuroTycho full raw ZIP archive bodies now present
under `_incoming/kanai_manual_transfer/KTMD/` and prepares a stable local
reference view under `data/raw/ktmd_neurotycho/`.

No raw data were moved, rewritten, expanded, or committed to Git. The
`data/raw/ktmd_neurotycho/` files are symlinks to the intake copies.

## Verdict

Status: `CONFIRMED LOCAL FULL-ZIP RAW ARCHIVES`.

- 11 KTMD raw ZIP archives are present locally.
- Total size is 16,234,100,968 bytes.
- All 11 filenames, sizes, and SHA-256 hashes match
  `_incoming/data_info/google_drive_inventory/NEUROTYCHO_SPLIT80MIB_MASTER_INDEX_SUMMARY.csv`.
- All 11 also match `pipeline/expected_master_index.json` inside
  `_incoming/kanai_manual_transfer/various_data/KTMD_ANALYSIS_CODE_COMPLETE_20260819.zip`.
- The six Kin2/Su corrected-montage target archives also match the 20260817
  result provenance table:
  `_incoming/from_local_not_organized/KTMD_Kin2_Su_CorrectedMontage_FINAL_HANDOFF_20260817 (1)/KTMD_Kin2_Su_CorrectedMontage_FullRerun_20260817/tables/RAW_ARCHIVE_PROVENANCE_ALL_SIX_DAYS.csv`.

## Prepared Local View

Prepared path:

`data/raw/ktmd_neurotycho/`

Source intake path:

`_incoming/kanai_manual_transfer/KTMD/`

Metadata manifest:

`data/metadata/KTMD_NEUROTYCHO_RAW_ARCHIVE_MANIFEST_2026-08-25.csv`

The six corrected-montage target days are:

| Animal | Date | Size bytes | SHA-256 |
| --- | --- | ---: | --- |
| Kin2 | 20110513 | 1424437299 | `02d72d7964fe7892d2cfdc2144d242f946658d50a931344972ea398627e4294b` |
| Kin2 | 20110524 | 1428485472 | `bf660e272e25843da01f3374de3374e3fdfd4e3a1a84aed3eab6ed1ba558e070` |
| Kin2 | 20110525 | 1702784580 | `216a77f81e8b0b62bf01d832b3bf780d292085a06b8cc3d5b07421a4040dd295` |
| Su | 20110523 | 1710588003 | `5627bc81c3b05a014582f077a95cc4a9ee4438062e2ccdb7f3b8dab73bc83a2f` |
| Su | 20110526 | 1641869102 | `5622f605e436d667b160124fdacd699e354bfe410e4172dfe7777e28cbaeb447` |
| Su | 20110527 | 1631726016 | `683fb88ae99ecc7df3b20c91a531907410150a304ffba3d55920209b1613a2b8` |

## Verification Commands

Full raw archive hashes were computed with:

```bash
shasum -a 256 _incoming/kanai_manual_transfer/KTMD/*ECoG128.zip
```

Structured comparison was run against the Drive master index summary, the code
bundle expected index, and the 20260817 six-day result provenance table.

Observed summary:

```text
ktmd_dir _incoming/kanai_manual_transfer/KTMD
raw_zip_count 11
raw_total_size_bytes 16234100968
expected_master_count 11
code_expected_count 11
six_day_provenance_count 6
six_day_target_count_found 6
missing_expected_archives 0
extra_raw_archives 0
target_total_size_bytes 9539890472
comparison_errors 0
```

Symlink validation:

```text
resolved_symlink_count 11
```

## Limitation

The original 20260819 pipeline entry point expects a split archive root and
reassembles split parts during execution. The current local preparation confirms
the full ZIP archive bodies, not the original 200 split-part files. For a full
rerun, either provide the original split-part tree or create and review an
adapter/re-splitting step before running the pipeline.
