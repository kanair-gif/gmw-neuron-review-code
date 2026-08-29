# Figure 1 Arrow Alignment and Awake k=3 Spatial Candidate

Date: 2026-08-30 Asia/Tokyo

## Scope

User-requested final figure touch:

- In Figure 1A, move the cyan input-arrow heads so they are no longer hidden under the central ellipse.
- Align the `Auditory` and `Value` boxes vertically with their arrows.
- Create a review-only candidate figure showing where the Awake k=3 macaque GMW candidates are located across all animals, using a Figure S9-like spatial display. Do not insert this candidate into the manuscript yet.

## Figure 1 Changes

Edited source script:

- `manuscript/submission/neuron_v22_candidate/working_copy/release_zip/GMW_Neuron_V22_release_dir/build/make_fig1_candidateb_imagebase.py`

New derived Figure 1 source art:

- `figures_source/figures_v14/fig1_gmw_boundary_hankel_candidateb_imagebase_20260830_arrowalign.png`
- `figures_source/figures_v14/fig1_gmw_boundary_hankel_candidateb_textoverlay_20260830_arrowalign.pdf`
  - SHA-256: `d34a8cf5e121a25c5590433baee0e9bc50ddfa71e4f87c7eaea7f69a81156793`
- `figures_source/figures_v14/fig1_gmw_boundary_hankel_candidateb_textoverlay_20260830_arrowalign.png`
  - SHA-256: `b2f53ae8acb277b2af06edccd0e49cecd4bbca88d58dd9e389ed10d3650b7456`

Active manuscript figure:

- `figures_main/Figure_1.pdf`
  - SHA-256: `ba53d6b71630595efbe3d2c81440ee7b583e9edae3b7419cc25c4d83fbdb0fae`

The immediately prior active Figure 1 PDF was retained at:

- `figures_main/Figure_1_pre_arrowalign_20260830.pdf`

## Review-Only Awake k=3 Candidate Figure

Generated script:

- `manuscript/submission/neuron_v22_candidate/working_copy/release_zip/GMW_Neuron_V22_release_dir/build/make_awake_k3_gmw_distribution_candidate.py`

Source tables:

- `.../tables/updated_same_animal_leave_one_day_out_candidates.csv`
- `.../tables/updated_panel_registered_contact_frequency.csv`

Construction:

- Filtered same-animal LODO candidates to `k=3`.
- Parsed bipolar-pair endpoint contacts from the `nodes` column.
- Counted contact recurrence as selected held-out folds / available held-out folds per animal.
- Mapped contacts to the registered common template coordinates.

Output:

- `figures_source/figures_macaque_officialmap/figS9_awake_k3_gmw_distribution_candidate_20260830.pdf`
  - SHA-256: `b965955301f70032cd13f8573b8eee2d3a733144bdb943058c4a8d1a2de423dd`
- `figures_source/figures_macaque_officialmap/figS9_awake_k3_gmw_distribution_candidate_20260830.png`
  - SHA-256: `57a99c427d85ec36894b2a759eeac0c9af1c9bd8ffeff4c39595629a206b5c23`
- `figures_source/figures_macaque_officialmap/figS9_awake_k3_gmw_distribution_candidate_20260830_source.csv`
  - SHA-256: `3525d386a8dff6fef15203779eb327e330f5c3322511315ef34db71045a317f6`

Rows in generated source CSV:

- 42 contact rows total.
- By animal: George 12, Chibi 10, Kin2 10, Su 10.
- By panel: lateral 40, medial 2.
- Coordinate lookup missing contacts: 0.

Status:

- This candidate was copied to `GMW_Neuron_V23_review_20260830/review_candidates/`.
- It was not inserted into `supplemental_information.tex`, `main.tex`, or the integrated manuscript.

## Rebuilt PDFs

Release working copy:

- `main.pdf`
  - SHA-256: `f3468ee3d0a7277c40e0d55cdf94d0a21b115e03028c8611433862bfe5fbba9f`
  - Pages: 21
- `supplemental_information.pdf`
  - SHA-256: `a0218cc027c97cd3f606b5b3bd682b34018fd5702951253dd39ce153ca68231e`
  - Pages: 25
- `GMW_Neuron_V22_integrated_submission.pdf`
  - SHA-256: `9802d9c81a95091258afcdb3c600b8bb51e485782bf68c7985f0d8d85f300d13`
  - Pages: 45

The rebuilt main and integrated PDFs were synced to the submission working copy and V23 review snapshot.

## QA

- Main PDF page 3 was rendered at 180 dpi and visually checked.
- Figure 1A cyan input-arrow heads are visible outside the central ellipse.
- `Auditory` and `Value` boxes now align more closely with their corresponding arrows.
- The generated Awake k=3 candidate PNG was visually checked; legends and points are readable, and no manuscript insertion was made.
- Tectonic emitted the known `lineno.sty` invalid UTF-8 warning during main/integrated builds, but both PDF builds completed.
- Raw data and source result tables were read only; no raw data files were modified.
