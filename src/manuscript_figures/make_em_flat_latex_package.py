#!/usr/bin/env python3
"""Build a flat Editorial Manager LaTeX source package for the V23 snapshot.

The editing/release tree intentionally uses subdirectories. Editorial Manager's
LaTeX upload route is more brittle, so this script creates a separate
upload-only package with TeX sources and all referenced graphics in one level.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path


DATE_TAG = "20260830"
SOURCE_PACKAGE_NAME = "GMW_Neuron_V23_EM_flat_latex_source"
UPLOAD_PACKAGE_NAME = "GMW_Neuron_V23_EM_upload_20260830"

INCLUDEGRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}")
GRAPHICSPATH_RE = re.compile(r"\\graphicspath\{((?:\{[^{}]*\})+)\}")
GRAPHICSPATH_ENTRY_RE = re.compile(r"\{([^{}]*)\}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    safe = re.sub(r"_+", "_", safe).strip("._")
    if not safe or "." not in safe:
        raise ValueError(f"Cannot make a safe filename from {name!r}")
    stem, suffix = Path(safe).stem, Path(safe).suffix
    stem = stem.replace(".", "_")
    safe = f"{stem}{suffix}"
    if len(safe) > 80:
        raise ValueError(f"Filename remains longer than 80 characters: {safe}")
    return safe


def graphicspaths(tex_text: str) -> list[Path]:
    paths: list[Path] = [Path(".")]
    for match in GRAPHICSPATH_RE.finditer(tex_text):
        for entry in GRAPHICSPATH_ENTRY_RE.findall(match.group(1)):
            if entry:
                paths.append(Path(entry))
    return paths


def candidate_paths(release_dir: Path, graphic_paths: list[Path], raw_arg: str) -> list[Path]:
    arg_path = Path(raw_arg)
    suffixes = [""]
    if not arg_path.suffix:
        suffixes = [".pdf", ".png", ".jpg", ".jpeg"]

    candidates: list[Path] = []
    for suffix in suffixes:
        candidate_arg = Path(str(arg_path) + suffix)
        if candidate_arg.is_absolute():
            candidates.append(candidate_arg)
        else:
            candidates.append(release_dir / candidate_arg)
            for graphic_path in graphic_paths:
                candidates.append(release_dir / graphic_path / candidate_arg)

    seen: set[Path] = set()
    existing: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists():
            existing.append(resolved)

    if existing:
        return existing

    basename_matches = sorted(release_dir.rglob(arg_path.name))
    return [p.resolve() for p in basename_matches if p.is_file()]


def copy_unique(source: Path, dest: Path) -> None:
    if dest.exists():
        if sha256(source) != sha256(dest):
            raise ValueError(f"Destination collision with different bytes: {dest}")
        return
    shutil.copy2(source, dest)


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def main() -> int:
    build_dir = Path(__file__).resolve().parent
    release_dir = build_dir.parent
    working_copy_dir = release_dir.parent.parent
    top_level_dir = working_copy_dir / "top_level"
    review_dir = top_level_dir / f"GMW_Neuron_V23_review_{DATE_TAG}"
    upload_dir = top_level_dir / UPLOAD_PACKAGE_NAME
    flat_dir = upload_dir / SOURCE_PACKAGE_NAME
    flat_zip = upload_dir / f"{SOURCE_PACKAGE_NAME}.zip"

    if upload_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing package: {upload_dir}")
    flat_dir.mkdir(parents=True)

    source_tex_specs = [
        (release_dir / "main.tex", "main.tex"),
        (release_dir / "supplemental_information.tex", "supplemental_information.tex"),
        (
            release_dir / "GMW_Neuron_V22_integrated_submission.tex",
            "GMW_Neuron_V23_integrated_submission.tex",
        ),
    ]
    aux_sources = [
        (release_dir / "references.bib", "references.bib"),
        (release_dir / "cell.bst", "cell.bst"),
        (release_dir / "main.bbl", "main.bbl"),
        (release_dir / "supplemental_information.bbl", "supplemental_information.bbl"),
    ]

    missing = [str(src) for src, _ in source_tex_specs + aux_sources if not src.exists()]
    if missing:
        raise FileNotFoundError("Required source files missing:\n" + "\n".join(missing))

    asset_to_dest: dict[Path, str] = {}
    dest_to_asset: dict[str, Path] = {}
    include_rewrites: dict[tuple[Path, str], str] = {}
    asset_rows: list[dict[str, str]] = []

    for tex_src, tex_dest_name in source_tex_specs:
        text = tex_src.read_text(encoding="utf-8")
        paths = graphicspaths(text)
        for match in INCLUDEGRAPHICS_RE.finditer(text):
            raw_arg = match.group(1).strip()
            matches = candidate_paths(release_dir, paths, raw_arg)
            if not matches:
                raise FileNotFoundError(f"Could not resolve graphic {raw_arg!r} from {tex_src}")
            graphic_src = matches[0]
            dest_name = asset_to_dest.get(graphic_src)
            if dest_name is None:
                base_name = sanitize_filename(graphic_src.name)
                dest_name = base_name
                if dest_name in dest_to_asset and dest_to_asset[dest_name] != graphic_src:
                    stem = Path(base_name).stem
                    suffix = Path(base_name).suffix
                    index = 2
                    while True:
                        candidate_name = f"{stem}_{index}{suffix}"
                        if len(candidate_name) > 80:
                            raise ValueError(f"Collision-safe filename too long: {candidate_name}")
                        if candidate_name not in dest_to_asset:
                            dest_name = candidate_name
                            break
                        index += 1
                asset_to_dest[graphic_src] = dest_name
                dest_to_asset[dest_name] = graphic_src
                copy_unique(graphic_src, flat_dir / dest_name)
                asset_rows.append(
                    {
                        "package_filename": dest_name,
                        "source_path": str(graphic_src.relative_to(release_dir)),
                        "size_bytes": str(graphic_src.stat().st_size),
                        "sha256": sha256(graphic_src),
                    }
                )
            include_rewrites[(tex_src, raw_arg)] = dest_name

    for tex_src, tex_dest_name in source_tex_specs:
        text = tex_src.read_text(encoding="utf-8")

        def replace_include(match: re.Match[str]) -> str:
            raw_arg = match.group(1).strip()
            dest_name = include_rewrites[(tex_src, raw_arg)]
            return match.group(0).replace("{" + match.group(1) + "}", "{" + dest_name + "}")

        rewritten = INCLUDEGRAPHICS_RE.sub(replace_include, text)
        rewritten = GRAPHICSPATH_RE.sub(r"\\graphicspath{{./}}", rewritten)
        if tex_dest_name == "GMW_Neuron_V23_integrated_submission.tex":
            rewritten = rewritten.replace("Auto-generated integrated Neuron V22 source.", "Auto-generated integrated Neuron V23 flat EM source.")
            rewritten = rewritten.replace("Generated from release main.tex and supplemental_information.tex on 2026-08-24 Asia/Tokyo.", "Flattened for Editorial Manager from the current V23 release working copy on 2026-08-30 Asia/Tokyo.")
        write_text(flat_dir / tex_dest_name, rewritten)

    for src, dest_name in aux_sources:
        copy_unique(src, flat_dir / dest_name)

    source_rows: list[dict[str, str]] = []
    for path in sorted(flat_dir.iterdir()):
        source_rows.append(
            {
                "package_filename": path.name,
                "size_bytes": str(path.stat().st_size),
                "sha256": sha256(path),
                "role": "latex_or_bibliography" if path.suffix.lower() in {".tex", ".bib", ".bst", ".bbl"} else "figure_asset",
            }
        )

    with flat_zip.open("wb"):
        pass
    with zipfile.ZipFile(flat_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(flat_dir.iterdir()):
            zf.write(path, arcname=path.name)

    compiled_pdf_specs = [
        (review_dir / "GMW_Neuron_V23_Combined_Submission.pdf", "GMW_Neuron_V23_Combined_Submission.pdf"),
        (review_dir / "GMW_Neuron_V23_Main.pdf", "GMW_Neuron_V23_Main.pdf"),
        (review_dir / "GMW_Neuron_V23_Supplement.pdf", "GMW_Neuron_V23_Supplement.pdf"),
    ]
    submission_specs = [
        (release_dir / "submission" / "cover_letter.docx", "cover_letter.docx"),
        (release_dir / "submission" / "cover_letter.pdf", "cover_letter.pdf"),
        (release_dir / "submission" / "highlights_and_in_brief.docx", "highlights_and_in_brief.docx"),
        (release_dir / "submission" / "highlights_and_in_brief.pdf", "highlights_and_in_brief.pdf"),
        (release_dir / "submission" / "graphical_abstract.png", "graphical_abstract.png"),
        (release_dir / "submission" / "graphical_abstract.pdf", "graphical_abstract.pdf"),
        (release_dir / "submission" / "submission_checklist.docx", "submission_checklist.docx"),
        (release_dir / "submission" / "submission_checklist.pdf", "submission_checklist.pdf"),
    ]
    copied_upload_items: list[Path] = [flat_zip]
    for src, dest_name in compiled_pdf_specs + submission_specs:
        if src.exists():
            dest = upload_dir / dest_name
            copy_unique(src, dest)
            copied_upload_items.append(dest)

    item_rows = [
        {
            "filename": f"{SOURCE_PACKAGE_NAME}.zip",
            "recommended_em_item": "LaTeX source / Manuscript source package",
            "notes": "Flat zip; assign TeX/BibTeX/BST/BBL as Manuscript items and graphics as Figure items if EM expands the package.",
        },
        {
            "filename": "GMW_Neuron_V23_Combined_Submission.pdf",
            "recommended_em_item": "Manuscript PDF / initial submission PDF",
            "notes": "Recommended checked review PDF containing main text and supplemental information.",
        },
        {
            "filename": "GMW_Neuron_V23_Main.pdf",
            "recommended_em_item": "Manuscript PDF alternative",
            "notes": "Use only if EM asks for main manuscript separately rather than a combined PDF.",
        },
        {
            "filename": "GMW_Neuron_V23_Supplement.pdf",
            "recommended_em_item": "Supplemental Information",
            "notes": "Use if EM asks for supplemental information as a separate file.",
        },
        {
            "filename": "cover_letter.docx / cover_letter.pdf",
            "recommended_em_item": "Cover Letter",
            "notes": "Use the format EM requests; do not include in reviewer PDF unless EM explicitly does so.",
        },
        {
            "filename": "highlights_and_in_brief.docx / highlights_and_in_brief.pdf",
            "recommended_em_item": "Highlights / In Brief if requested",
            "notes": "Current local artifact is inherited from the release working copy.",
        },
        {
            "filename": "graphical_abstract.png / graphical_abstract.pdf",
            "recommended_em_item": "Graphical Abstract / eTOC image if requested",
            "notes": "PNG is 1200 x 1200 px in the audited package.",
        },
        {
            "filename": "submission_checklist.docx / submission_checklist.pdf",
            "recommended_em_item": "Administrative checklist if requested",
            "notes": "Do not upload unless EM asks for this item.",
        },
        {
            "filename": "Declaration of Interests PDF",
            "recommended_em_item": "Declaration of Interests",
            "notes": "MISSING from the local package; complete the Elsevier/Cell Press DOI form before final submission.",
        },
    ]

    with (upload_dir / "EM_UPLOAD_ITEM_MAP.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["filename", "recommended_em_item", "notes"])
        writer.writeheader()
        writer.writerows(item_rows)

    with (upload_dir / "EM_FLAT_LATEX_MANIFEST.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["package_filename", "size_bytes", "sha256", "role"])
        writer.writeheader()
        writer.writerows(source_rows)

    with (upload_dir / "EM_FLAT_GRAPHICS_SOURCE_MAP.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["package_filename", "source_path", "size_bytes", "sha256"])
        writer.writeheader()
        writer.writerows(sorted(asset_rows, key=lambda row: row["package_filename"]))

    all_hash_rows = []
    for path in sorted(upload_dir.iterdir()):
        if path.is_file():
            all_hash_rows.append(f"{sha256(path)}  {path.name}")
    write_text(upload_dir / "SHA256SUMS.txt", "\n".join(all_hash_rows) + "\n")

    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    readme = f"""# GMW Neuron V23 EM Upload Package

Created: {created_at}

This directory is an upload-only staging area for Neuron / Elsevier Editorial Manager. It does not replace the editable release working copy.

## Main File To Use For LaTeX Source Upload

- `{SOURCE_PACKAGE_NAME}.zip`

The zip is flat: all `.tex`, `.bib`, `.bst`, `.bbl`, PDF, and PNG files are at the archive root. The TeX files have `\\graphicspath{{{{./}}}}`, and every `\\includegraphics` argument is a bare filename.

## Important Upload Notes

- Do not upload `GMW_Neuron_V23_review_{DATE_TAG}.zip` or the release working copy as the EM LaTeX source package; those trees use subfolders.
- If EM expands the source package into individual items, assign `.tex`, `.bib`, `.bst`, and `.bbl` files as Manuscript/source items, and assign image/PDF figure assets as Figure items. Do not assign LaTeX source files as Supplemental items.
- Use `GMW_Neuron_V23_Combined_Submission.pdf` as the checked initial manuscript PDF unless EM requires main and supplement to be separate.
- A completed Declaration of Interests PDF was not found locally and still needs to be added before final submission.
- The review-only Awake k=3 candidate spatial figure was intentionally omitted because it is not inserted in the manuscript.

## QA Files

- `EM_FLAT_LATEX_MANIFEST.csv`: all files inside the flat source zip with SHA-256 hashes.
- `EM_FLAT_GRAPHICS_SOURCE_MAP.csv`: source path for each copied graphic asset.
- `EM_UPLOAD_ITEM_MAP.csv`: suggested Editorial Manager item assignments.
- `SHA256SUMS.txt`: hashes for this upload staging directory's top-level files.
"""
    write_text(upload_dir / "README_EM_UPLOAD.md", readme)

    summary = {
        "created_at": created_at,
        "release_dir": str(release_dir),
        "review_dir": str(review_dir),
        "upload_dir": str(upload_dir),
        "flat_source_dir": str(flat_dir),
        "flat_source_zip": str(flat_zip),
        "flat_source_zip_sha256": sha256(flat_zip),
        "flat_source_zip_size_bytes": flat_zip.stat().st_size,
        "flat_source_file_count": len(source_rows),
        "referenced_graphics_count": len(asset_rows),
        "copied_upload_items": [path.name for path in copied_upload_items],
        "missing_required_before_submission": ["Declaration of Interests PDF"],
        "omitted_review_only_candidates": [
            "GMW_Neuron_V23_review_20260830/review_candidates/figS9_awake_k3_gmw_distribution_candidate_20260830.pdf"
        ],
    }
    write_text(upload_dir / "EM_PACKAGE_SUMMARY.json", json.dumps(summary, indent=2) + "\n")

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
