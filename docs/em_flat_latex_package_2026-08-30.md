# EM Flat LaTeX Package

Date: 2026-08-30 Asia/Tokyo

## Purpose

Create a Neuron / Elsevier Editorial Manager upload-only file set from the current V23 review materials. This package exists because the editable release working copy uses subfolders, while the EM LaTeX upload route was confirmed to require a flat source package.

## Created Artifacts

Upload staging directory:

- `manuscript/submission/neuron_v22_candidate/working_copy/top_level/GMW_Neuron_V23_EM_upload_20260830/`

Primary LaTeX source package:

- `GMW_Neuron_V23_EM_flat_latex_source.zip`
- SHA-256: `2880483687754eb77c37894142552deb564d7372a9fa70b76d9ae2f65cb1f8c0`
- Size: 2,316,254 bytes
- Archive layout: flat root only, no subdirectories
- Contents: 27 files total, including 3 `.tex` files, `references.bib`, `cell.bst`, `main.bbl`, `supplemental_information.bbl`, and 20 referenced figure assets

Checked PDF copies in the upload staging directory:

- `GMW_Neuron_V23_Combined_Submission.pdf`
  - SHA-256: `d669cb6240a69a4720c61b641ab8f63a526b39c51d8c1ce385ef50547de200d3`
- `GMW_Neuron_V23_Main.pdf`
  - SHA-256: `918446d771c212280e05127a1ebbb455fc8e6607ea67077322ed846d097e71f8`
- `GMW_Neuron_V23_Supplement.pdf`
  - SHA-256: `a0218cc027c97cd3f606b5b3bd682b34018fd5702951253dd39ce153ca68231e`

Additional upload-staging files copied from the current release working copy:

- `cover_letter.docx`
- `cover_letter.pdf`
- `highlights_and_in_brief.docx`
- `highlights_and_in_brief.pdf`
- `graphical_abstract.png`
- `graphical_abstract.pdf`
- `submission_checklist.docx`
- `submission_checklist.pdf`

Manifests and instructions:

- `README_EM_UPLOAD.md`
- `EM_UPLOAD_ITEM_MAP.csv`
- `EM_FLAT_LATEX_MANIFEST.csv`
- `EM_FLAT_GRAPHICS_SOURCE_MAP.csv`
- `EM_PACKAGE_SUMMARY.json`
- `SHA256SUMS.txt`

## Package Construction

Script:

- `manuscript/submission/neuron_v22_candidate/working_copy/release_zip/GMW_Neuron_V22_release_dir/build/make_em_flat_latex_package.py`

Source tree:

- `manuscript/submission/neuron_v22_candidate/working_copy/release_zip/GMW_Neuron_V22_release_dir/`

The script copied the current `main.tex`, `supplemental_information.tex`, and generated integrated source as `GMW_Neuron_V23_integrated_submission.tex`. It rewrote `\graphicspath` to `{{./}}` and rewrote every `\includegraphics` argument to a bare filename. Graphics were resolved from the release working copy's declared `\graphicspath` entries, then copied into the flat package with safe filenames.

## QA

Flat package checks:

- `zipinfo -1` showed no subdirectory entries.
- Parser check found no `\includegraphics` argument containing `/` or `\`.
- Parser check confirmed every referenced graphic exists inside the flat source directory.
- Filename check found no names longer than 80 characters, no special characters beyond ASCII letters/numbers/underscore/hyphen/period, and no filenames with multiple periods.
- The old `Figure_6.pdf` provenance artifact and the review-only `figS9_awake_k3_gmw_distribution_candidate_20260830.pdf` are not in the flat source package because they are not referenced by the current manuscript.

Build checks from an extracted copy of the current flat zip in `/private/tmp/gmw_em_flat_build_final_20260830/`:

- `main.tex` rebuilt with Tectonic: 21 pages.
- `supplemental_information.tex` rebuilt with Tectonic: 25 pages.
- `GMW_Neuron_V23_integrated_submission.tex` rebuilt with Tectonic: 45 pages.
- Known `lineno.sty` invalid UTF-8 warning appeared for main/integrated builds and did not prevent PDF creation.
- Supplement build emitted the existing `xr-hyper` package-order warning and completed successfully.
- Render QA spot checks at 150 dpi: main page 3, main page 6, supplement page 14, and supplement page 23. Figure 1 and Figure 2 rendered normally; Supplementary Figure S13B retained grid lines behind bars.
- PDF text extraction from the flat-built main and integrated PDFs found `generative AI` before `References`.
- PDF text extraction from the flat-built main and integrated PDFs found the public GitHub code URL and found no remaining legacy no-public-code or lead-contact-only access wording.
- Render QA at 180 dpi for current main PDF pages 15--16 confirmed the Resource availability and Key resources table pages render without layout breakage after the public-code URL update.

## EM Item Guidance

- Use `GMW_Neuron_V23_EM_flat_latex_source.zip` for the EM LaTeX source upload route.
- If EM expands the zip into individual items, assign `.tex`, `.bib`, `.bst`, and `.bbl` files as Manuscript/source items and PDF/PNG figure assets as Figure items.
- Do not assign LaTeX source files as Supplemental items.
- Use `GMW_Neuron_V23_Combined_Submission.pdf` as the checked initial manuscript PDF unless EM requires separate main and supplemental PDFs.
- Do not upload the subfolder-based V23 review snapshot zip or release working copy as the EM LaTeX source package.

## Still Missing Or Waiting

- A completed Cell Press / Elsevier Declaration of Interests PDF is present in the upload staging directory as `declaration_of_interests_form.pdf` and matches the manuscript statement: `R.K. is founder and chief executive officer of Araya Inc.`
- Logged-in EM checklist/category fields still need final reconciliation before actual submission.
- Ryota's final full-manuscript read-through and final declaration/funding/acknowledgment confirmation remain pending.
- The review-only Awake k=3 spatial candidate figure was judged visually unsuitable for now because it is not on the same brain template. It remains outside the manuscript and source package; a better template-matched version can be generated later.
