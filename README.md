# single-chapter-remover

Scans MP4 files recursively and removes spurious single-chapter metadata — no re-encoding, no quality loss.

Some tools (encoders, editors, download clients) embed a single, unnecessary chapter marker in MP4 files. This may confuses media players and home-theatre software. This tool detects those files via `ffprobe` and strips the chapter track with `ffmpeg -map_chapters -1 -c copy`.

## Quick start

### Docker (recommended)

```yaml
# docker-compose.yml
services:
  single-chapter-remover:
    image: ghcr.io/doctorkomodo/single-chapter-remover:latest
    environment:
      MEDIA_PATHS: "/media/movies:/media/tv"
    volumes:
      - /path/to/your/movies:/media/movies
      - /path/to/your/tv:/media/tv
    restart: "no"
```

```bash
docker compose up
```

The container runs once, processes all MP4 files, and exits.

### Python (local)

Requirements: Python 3.10+, `ffmpeg` / `ffprobe` on your `PATH`.

```bash
pip install APScheduler==3.10.4
python fix_single_chapters.py --paths /media/movies:/media/tv
```

### PowerShell (Windows)

```powershell
.\fix-single-chapters.ps1 -Path "D:\Movies"
```

## Configuration

All options can be set via environment variables (Docker) or CLI flags (Python). CLI flags take precedence.

| Env var | CLI flag | Default | Description |
|---------|----------|---------|-------------|
| `MEDIA_PATHS` | `--paths` | *(required)* | Colon-separated list of directories to scan |
| `SCHEDULE` | `--schedule` | *(empty — single-shot)* | Cron (`"0 3 * * *"`) or interval (`"6h"`, `"30m"`, `"90s"`) |
| `SCAN_ONLY` | `--scan-only` | `false` | Dry-run: report without modifying files |
| `IGNORE_CACHE` | `--ignore-cache` | `false` | Re-check all files, ignoring cache |
| `LOG_LEVEL` | — | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `PUID` | — | `1000` | UID the container process runs as |
| `PGID` | — | `1000` | GID the container process runs as |

## Run modes

### Single-shot (default)

Scans all paths once and exits. Use `restart: "no"` in Compose (the default).

```yaml
SCHEDULE: ""
```

### Scheduled

Keeps the container running and re-scans on a schedule.

```yaml
SCHEDULE: "0 3 * * *"   # cron: daily at 03:00 UTC
# or
SCHEDULE: "6h"          # interval: every 6 hours
restart: "unless-stopped"
```

> **Warning:** Do not use `restart: always` or `restart: unless-stopped` with single-shot mode. Docker restarts containers on exit code 0, causing an infinite loop.

### Dry-run

Report files that would be changed without touching them.

```yaml
SCAN_ONLY: "true"
```

## Caching

To avoid re-scanning large libraries on every run, the tool writes a cache file into each scanned root directory:

| File | Purpose |
|------|---------|
| `checked-files.txt` | Paths of all previously inspected MP4 files (skipped on subsequent runs) |
| `single-chapter-files.txt` | Paths of files that had a single chapter (fixed or pending) |

Use `--ignore-cache` / `IGNORE_CACHE: "true"` to force a full re-scan.

## File permissions

By default the container process runs as UID/GID 1000. If your bind-mounted media directories are owned by a different user on the host, the container will fail to write the cache files or the modified MP4s. Fix this by setting `PUID` and `PGID` to match the host directory owner:

```bash
# Find your host UID/GID
id
# uid=1001(alice) gid=1001(alice) ...
```

```yaml
environment:
  PUID: "1001"
  PGID: "1001"
```

The container entrypoint remaps the internal process to the specified UID/GID at startup before the application runs, so no `chown` on the host is required.

## How it works

1. Recursively find all `.mp4` files under each configured path.
2. Skip files already present in `checked-files.txt`.
3. Run `ffprobe -show_chapters` on each file.
4. If exactly **1 chapter** is found:
   - **Fix mode** (default): run `ffmpeg -map_chapters -1 -c copy` to a temporary file, then atomically replace the original.
   - **Scan-only mode**: log a warning and record the file.
5. Record all inspected files in the cache.
6. Write a summary and the list of affected files to `single-chapter-files.txt`.

## Passing CLI flags via docker run

Configuration is intended to be set via environment variables (see [Configuration](#configuration) above). If you need to pass CLI flags directly, include the full command:

```bash
docker run --rm \
  -e MEDIA_PATHS="/media/movies" \
  -v /path/to/movies:/media/movies \
  ghcr.io/doctorkomodo/single-chapter-remover:latest \
  python fix_single_chapters.py --scan-only
```

## Building the image locally

```bash
docker build -t single-chapter-remover .
```

## License

[MIT](LICENSE)
