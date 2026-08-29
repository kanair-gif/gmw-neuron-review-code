# Global Mediation Workspace reviewer code

This repository provides anonymous, no-login access to the custom code, algorithms, and computational models underlying the manuscript:

**The Global Mediation Workspace: A control-theoretic formulation of global workspace theory**

The full prepared package is available in `gmw-neuron-review-code-20260830.zip` at the repository root. The most important instructions and provenance files are also shown directly in the repository so reviewers do not need an account or password to understand the contents.

## Contents

| Path | Purpose |
| --- | --- |
| `gmw-neuron-review-code-20260830.zip` | Complete prepared reviewer-code package, including code, small outputs, provenance notes, and checksums. |
| `src/synthetic_workspace/` | Standalone synthetic benchmark for the boundary-Hankel mediation score and confusable control networks. |
| `src/ktmd_corrected_montage/` | Corrected-montage macaque ECoG analysis code notes and entry points. Full code bundle is also in the ZIP. |
| `src/manuscript_figures/` | Manuscript figure script notes. Full script copy is also in the ZIP. |
| `data/README.md` | Raw-data access and checksum guidance. |
| `docs/` | Audit notes and provenance summaries. |

## Quick start

Download and extract `gmw-neuron-review-code-20260830.zip`, then create a Python environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the standalone synthetic benchmark from the extracted package:

```bash
cd src/synthetic_workspace
python workspace_core_experiment.py --output-dir results_quick
```

The full synthetic benchmark, including repeated beam searches and exact four-node enumeration, can be run with:

```bash
python workspace_core_experiment.py --output-dir results_full --full
```

## Macaque ECoG analysis

The macaque ECoG analysis code in the package is under:

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

The full rerun requires source NeuroTycho raw archives or split archive parts listed in `pipeline/expected_master_index.json`. See `data/README.md` and `docs/KTMD_RAW_LOCALIZATION_VERIFICATION_2026-08-25.md` for the checksum-based provenance record used for the submitted manuscript.

## Access statement

This repository is public on GitHub. Reviewers can open it, download the ZIP, or clone it without providing a personal login, password, or contact information:

```bash
git clone https://github.com/kanair-gif/gmw-neuron-review-code.git
```

Direct ZIP download:

```text
https://raw.githubusercontent.com/kanair-gif/gmw-neuron-review-code/main/gmw-neuron-review-code-20260830.zip
```

## Limits

- Raw third-party NeuroTycho ECoG data are not included.
- Large derived working directories are not included.
- Some figure scripts require manuscript-local paths and are included for source auditability.
- No credential, private login, or reviewer-identifying information is required to use this repository.
