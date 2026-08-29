# Global Mediation Workspace reviewer code

This repository provides anonymous, no-login access to the custom code,
algorithms, and computational models underlying the manuscript:

**The Global Mediation Workspace: A control-theoretic formulation of global
workspace theory**

The repository is intentionally code-focused. It includes the synthetic network
benchmark, the macaque ECoG corrected-montage analysis code bundle, manuscript
figure-generation scripts, and provenance notes. Large third-party raw ECoG
archives are not redistributed here.

## Contents

| Path | Purpose |
| --- | --- |
| `src/synthetic_workspace/` | Standalone synthetic benchmark for the boundary-Hankel mediation score and confusable control networks. |
| `src/ktmd_corrected_montage/` | Corrected-montage macaque ECoG analysis code, provenance checks, and small configuration/result tables. |
| `src/manuscript_figures/` | Scripts and TeX wrappers used to redraw manuscript and supplementary figures. |
| `data/README.md` | Raw-data access and checksum guidance. |
| `docs/` | Audit notes, flat-TeX package provenance, raw archive verification notes, and manuscript-figure source maps. |

## Quick start

Create a Python environment and install the lightweight dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the standalone synthetic benchmark:

```bash
cd src/synthetic_workspace
python workspace_core_experiment.py --output-dir results_quick
```

The full synthetic benchmark, including repeated beam searches and exact
four-node enumeration, can be run with:

```bash
python workspace_core_experiment.py --output-dir results_full --full
```

## Macaque ECoG analysis

The macaque ECoG analysis code is in:

```text
src/ktmd_corrected_montage/KTMD_ANALYSIS_CODE_COMPLETE_20260819/
```

The top-level pipeline entry point is:

```bash
python pipeline/run_full_corrected_pipeline.py \
  --split-root <local NeuroTycho split-archive root> \
  --output-root <analysis output directory> \
  --assets pipeline \
  --work-root <scratch working directory>
```

The full rerun requires the source NeuroTycho raw archives or split archive
parts listed in `pipeline/expected_master_index.json`. See `data/README.md` and
`docs/KTMD_RAW_LOCALIZATION_VERIFICATION_2026-08-25.md` for the checksum-based
provenance record used for the submitted manuscript.

## Manuscript figures

`src/manuscript_figures/` contains plotting and TeX wrapper scripts used for the
current Neuron submission figures. Some scripts expect the full manuscript
working tree and derived result tables, so they are provided as auditable source
provenance rather than as a single fully self-contained figure rebuild package.

## Access statement

This repository is public on GitHub. Reviewers can open or clone it without
providing a personal login, password, or contact information:

```bash
git clone https://github.com/kanair-gif/gmw-neuron-review-code.git
```

The code and provenance files are also browsable directly in GitHub.

## Limits

- Raw third-party NeuroTycho ECoG data are not included.
- Large derived working directories are not included.
- Some figure scripts require manuscript-local paths and are included for source
  auditability.
- No credential, private login, or reviewer-identifying information is
  required to use this repository.
