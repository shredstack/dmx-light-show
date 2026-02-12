# Shows

This directory contains QLC+ workspace files (`.qxw`).

## Files

- **main-show.qxw** — A minimal empty workspace template. Open this in QLC+ as a starting point for manual show building.
- **Generated shows** — Files created by `scripts/generate_show_xml.py` will be saved here (e.g., `song1_show.qxw`).

## Opening a Show

1. Launch QLC+
2. File → Open Workspace
3. Select the `.qxw` file

## Manual vs. Generated Workflow

**Manual:** Open `main-show.qxw`, add your fixtures, create scenes and chasers by hand, and build your show in the Show Manager timeline. This gives you full creative control.

**Generated:** Run the Python pipeline (convert → analyze → generate) to produce a `.qxw` file with auto-placed lighting cues synced to beat analysis. Open the generated file in QLC+ to preview, then refine manually.

The two approaches combine well: generate a starting point, then fine-tune it in QLC+.

## Backups

QLC+ may reorder XML elements when saving. Keep backups of your `.qxw` files before making significant changes. QLC+ creates `.qxw.bak` files automatically (these are excluded from git via `.gitignore`).
