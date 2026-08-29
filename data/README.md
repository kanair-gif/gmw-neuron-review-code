# Data access and provenance

This repository does not redistribute raw macaque ECoG archives. The submitted manuscript analyzes third-party NeuroTycho anesthesia ECoG data. The complete reviewer-code ZIP records the exact expected raw archive identities in:

```text
src/ktmd_corrected_montage/KTMD_ANALYSIS_CODE_COMPLETE_20260819/pipeline/expected_master_index.json
```

The local manuscript audit verified 11 raw ZIP archive bodies by filename, size, and SHA-256 hash. The six corrected-montage Kin2/Su target archives were also matched against the 20260817 result provenance table. The public repository retains the checksum and provenance metadata needed to audit the code-data interface without bundling the raw data.

For a full macaque rerun:

1. Obtain the NeuroTycho raw archives or split archive parts corresponding to `expected_master_index.json`.
2. Verify filenames, sizes, and SHA-256 hashes before analysis.
3. Run the corrected-montage pipeline with `--split-root`, `--output-root`, `--assets`, and `--work-root` as described in the root `README.md`.

Raw-data redistribution and access terms are governed by the source dataset, not by this code repository.
