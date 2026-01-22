# Chemotion Converter Profiles & Readers Index

This repository builds and publishes a GitHub Pages site that documents Chemotion Converter profiles and readers. It collects metadata from JSON profiles and reader code, renders a Markdown index, and then produces a static HTML page in `docs/`.

## What This Repo Does
- Generates a readable index of available profiles and readers.
- Publishes the index to GitHub Pages on every push to `main`.
- Keeps profile metadata and readers in sync with the Converter package.

## Installation
This project depends on the `chemotion-converter-app` package (installed directly from GitHub) plus local Python tooling.

Requirements:
- Python 3.12
- Git (to install the Converter package from GitHub)

Steps:
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --no-cache-dir -r requirements.txt
```

The dependency on `chemotion-converter-app` is declared in `requirements.txt` and pulled from:
`git+https://github.com/ComPlat/chemotion-converter-app`.

## Folder Structure
```
.
├─ .github/workflows/        # GitHub Actions workflow for build + deploy
├─ build/                    # Generated Markdown artifacts (local output)
├─ data_files/               # Example and sample input files
├─ docs/                     # GitHub Pages output (generated)
├─ profile_manager/          # Build script, templates, and helpers
├─ profiles/                 # Profile JSON files (public + other sets)
├─ readers/                  # Local reader implementations (reference)
├─ requirements.txt          # Python dependencies
└─ README.md                 # Project documentation
```

## Build Workflow
The index is rebuilt whenever profiles change or new profiles are uploaded.

Local rebuild:
```bash
python -m profile_manager build_index
```

This command:
- Reads profiles from `profiles/public/`.
- Scans reader classes from the Converter package.
- Renders a Markdown index (`index.md`) and injects it into `docs/index.html`
  using `profile_manager/index_template.html`.

## GitHub Pages Workflow (Rebuild on Push)
The GitHub Actions workflow in `/.github/workflows/build_and_deploy.yml` runs on:
- Every push to `main`.
- Manual workflow dispatch.

On each run, it installs dependencies, builds the index, and publishes the
contents of `docs/` to GitHub Pages. This means every profile upload or change
that gets pushed to `main` automatically triggers a rebuild and redeploy.

---
Created: 2026-01-22  
Last updated: 2026-01-22
