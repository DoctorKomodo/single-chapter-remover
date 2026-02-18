# CRITICAL

RESPECT THE WORKFLOW BELOW!!!
NEVER: leave uncommitted or unpushed changes - always maintain a consistent and backed-up repository state
ALWAYS: Consider if a web research for current best practices could be useful.
ALWAYS: Consider if a web research for existing framework components that cover the requirements

# PROJECT OVERVIEW

**single-chapter-remover** removes spurious single-chapter metadata from MP4 files without re-encoding. It is available as:

- `fix_single_chapters.py` — cross-platform Python CLI / Docker entrypoint
- `fix-single-chapters.ps1` — PowerShell script for Windows users

Key dependencies: `ffprobe` / `ffmpeg` (runtime), `APScheduler` (optional scheduling).

## Important files

| File | Purpose |
|------|---------|
| `fix_single_chapters.py` | Main Python implementation |
| `fix-single-chapters.ps1` | PowerShell implementation (Windows) |
| `Dockerfile` | Docker image (python:3.12-slim + ffmpeg) |
| `docker-compose.yml` | Reference Compose configuration |
| `requirements.txt` | Python dependencies (APScheduler) |

## Environment variables / CLI flags

| Env var | CLI flag | Default | Description |
|---------|----------|---------|-------------|
| `MEDIA_PATHS` | `--paths` | *(required)* | Colon-separated list of directories to scan |
| `SCHEDULE` | `--schedule` | *(empty)* | Cron (`"0 3 * * *"`) or interval (`"6h"`, `"30m"`, `"90s"`). Empty = single-shot. |
| `SCAN_ONLY` | `--scan-only` | `false` | Dry-run: report without modifying files |
| `IGNORE_CACHE` | `--ignore-cache` | `false` | Re-check all files, ignoring cache |
| `LOG_LEVEL` | — | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## Cache files written per scanned directory

| File | Purpose |
|------|---------|
| `checked-files.txt` | Paths of all previously inspected MP4 files (skip on next run) |
| `single-chapter-files.txt` | Paths of files that had a single chapter (problem or fixed) |

# WORKFLOW

## Git Branching

- Work on feature branches, NOT directly on main/master
- Create a new branch for each task: `git checkout -b feature/<descriptive-name>`
- Commit changes to the feature branch with conventional commit messages
- Only merge to main when the user approves the changes
- After merge approval: merge to main with `--no-ff`, push, and delete the feature branch
- Keep feature branches focused on a single task/feature

## Code Review Process

After completing a task do two subsequent reviews:

1. **First**: review your changes with a subagent that focuses on the big picture, how the new implementation is used and which implications arise
2. **Second**: review your changes with a subagent the default way

Address findings and ask back if anything unclear.

## Testing

There is currently no automated test suite. When making changes:

- Run a quick smoke-test: mount a small directory of MP4 files and verify the script scans correctly with `--scan-only`
- Verify Docker image builds: `docker build -t single-chapter-remover .`
- Verify the Compose config is valid: `docker compose config`
- Confirm the PowerShell script still matches the Python behaviour for any logic changes
