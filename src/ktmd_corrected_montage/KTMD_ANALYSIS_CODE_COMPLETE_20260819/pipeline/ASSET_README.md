# Submission-ready corrected-montage full rerun v4

Every corrected day writes `RAW_ARCHIVE_PROVENANCE.json`. The final pipeline
requires all six expected animal/date identities, all part and archive SHA-256
checks, and six distinct raw archive hashes. It writes
`REAL_RAW_DATA_PROVENANCE_VERIFIED.ok` only after those checks and all numerical
and montage-QC audits pass. Pipeline smoke tests and duplicated-day placeholders
are rejected and must never be used as publication results.
