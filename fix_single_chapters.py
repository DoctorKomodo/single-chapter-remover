#!/usr/bin/env python3
"""
fix_single_chapters.py
Removes single-chapter metadata from MP4 files using ffprobe/ffmpeg.
Supports multiple scan paths, caching, and optional scheduled execution.
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CACHE_FILENAME = "checked-files.txt"
PROBLEM_FILENAME = "single-chapter-files.txt"

# ---------------------------------------------------------------------------
# ffprobe / ffmpeg helpers
# ---------------------------------------------------------------------------


def get_chapter_count(file_path: str) -> int:
    """Return the number of chapters in an MP4 file via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_chapters",
            file_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {file_path}: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    return len(data.get("chapters", []))


def strip_chapters(file_path: str) -> bool:
    """
    Remove all chapter metadata from file_path without re-encoding.
    Creates a temporary file first; replaces the original only on success.
    Returns True on success, False on failure.
    """
    temp_path = file_path + ".tmp.mp4"
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-i", file_path,
                "-map_chapters", "-1",
                "-c", "copy",
                temp_path,
                "-y",
                "-loglevel", "warning",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            # Atomic replace on POSIX — original is never left in a partial state
            os.replace(temp_path, file_path)
            return True
        else:
            logger.error("ffmpeg error for %s: %s", file_path, result.stderr.strip())
            return False
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def load_cache(cache_path: str) -> set:
    """Load previously checked file paths from the cache file."""
    if not os.path.exists(cache_path):
        return set()
    with open(cache_path, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def save_cache(cache_path: str, entries: set) -> None:
    """Persist the set of checked file paths to the cache file."""
    with open(cache_path, "w", encoding="utf-8") as f:
        for entry in sorted(entries):
            f.write(entry + "\n")

# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------


def process_path(path: str, scan_only: bool, ignore_cache: bool) -> None:
    """
    Scan a single directory tree for single-chapter MP4 files.
    Mirrors the behaviour of fix-single-chapters.ps1 exactly.
    """
    cache_path = os.path.join(path, CACHE_FILENAME)
    problem_path = os.path.join(path, PROBLEM_FILENAME)

    # Load cache
    cached_files: set = set()
    if not ignore_cache:
        cached_files = load_cache(cache_path)
        if cached_files:
            logger.info(
                "Loaded %d previously checked file(s) from cache (%s)",
                len(cached_files),
                cache_path,
            )

    problem_files: list[str] = []
    fixed_files: list[str] = []
    newly_checked: list[str] = []
    skipped_count = 0

    for mp4 in Path(path).rglob("*"):
        if not mp4.is_file() or mp4.suffix.lower() != ".mp4":
            continue
        file = str(mp4.resolve())

        if file in cached_files:
            skipped_count += 1
            logger.debug("Skipped (cached): %s", file)
            continue

        logger.info("Checking: %s", file)

        try:
            chapter_count = get_chapter_count(file)
        except Exception as exc:
            logger.error("Could not probe %s: %s", file, exc)
            # Do not cache — allow retry on next run
            continue

        if chapter_count == 1:
            if scan_only:
                logger.warning("  Single chapter found (scan only)")
                problem_files.append(file)
                # Do not cache — file hasn't been fixed; allow it to be caught on a future fix run
            else:
                logger.info("  Fixing...")
                if strip_chapters(file):
                    logger.info("  Done!")
                    fixed_files.append(file)
                    newly_checked.append(file)
                else:
                    logger.warning("  Failed!")
                    problem_files.append(file)
                    # Do not cache — fix failed; allow retry on next run
        else:
            logger.info("  OK (%d chapters)", chapter_count)
            newly_checked.append(file)

    # Update cache — only when new files were checked (matches PS behaviour)
    if newly_checked:
        all_checked = cached_files | set(newly_checked)
        save_cache(cache_path, all_checked)

    # Write problem/fixed file list
    all_problem_files = problem_files + fixed_files
    if all_problem_files:
        with open(problem_path, "w", encoding="utf-8") as f:
            for entry in all_problem_files:
                f.write(entry + "\n")

    # Summary
    logger.info("--- Summary for %s ---", path)
    logger.info("  Skipped (cached):  %d", skipped_count)
    logger.info("  Checked (new):     %d", len(newly_checked))
    logger.info("  Problems found:    %d", len(all_problem_files))
    if not scan_only and fixed_files:
        logger.info("    Fixed:           %d", len(fixed_files))
    if problem_files:
        label = "Pending" if scan_only else "Failed"
        logger.warning("    %s:         %d", label, len(problem_files))
    if all_problem_files:
        logger.info("  Results saved to:  %s", problem_path)
    logger.info("  Cache saved to:    %s", cache_path)


def run_all_paths(paths: list[str], scan_only: bool, ignore_cache: bool) -> int:
    """Process each path in sequence. Returns 1 if any path was invalid, else 0."""
    had_error = False
    for path in paths:
        if not os.path.isdir(path):
            logger.error("Path does not exist or is not a directory: %s", path)
            had_error = True
            continue
        logger.info("=== Processing path: %s ===", path)
        process_path(path, scan_only=scan_only, ignore_cache=ignore_cache)
    return 1 if had_error else 0

# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


def parse_schedule(schedule_str: str):
    """
    Parse a schedule string into an APScheduler trigger.
    Supports:
      - Interval format: "6h", "30m", "90s"
      - Cron format:     "0 3 * * *"
    Returns None if schedule_str is empty.
    """
    if not schedule_str:
        return None

    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    m = re.match(r'^(\d+)(h|m|s)$', schedule_str.strip())
    if m:
        value = int(m.group(1))
        unit = m.group(2)
        kwargs = {"hours": value} if unit == "h" else \
                 {"minutes": value} if unit == "m" else \
                 {"seconds": value}
        return IntervalTrigger(**kwargs)

    # Treat as cron expression
    return CronTrigger.from_crontab(schedule_str.strip())

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove single-chapter metadata from MP4 files."
    )
    parser.add_argument(
        "--paths",
        help="Colon-separated list of directories to scan (overrides MEDIA_PATHS env var)",
    )
    parser.add_argument(
        "--schedule",
        help=(
            "Run on a schedule. Accepts a cron expression (e.g. '0 3 * * *') "
            "or an interval (e.g. '6h', '30m', '90s'). "
            "Omit for single-shot mode. Overrides SCHEDULE env var."
        ),
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Dry-run: report single-chapter files without modifying them",
    )
    parser.add_argument(
        "--ignore-cache",
        action="store_true",
        help="Re-check all files, ignoring the existing cache",
    )
    args = parser.parse_args()

    # Resolve configuration — CLI args take precedence over env vars
    paths_str = args.paths or os.environ.get("MEDIA_PATHS", "")
    schedule_str = args.schedule if args.schedule is not None else os.environ.get("SCHEDULE", "")
    scan_only = args.scan_only or os.environ.get("SCAN_ONLY", "").lower() == "true"
    ignore_cache = args.ignore_cache or os.environ.get("IGNORE_CACHE", "").lower() == "true"

    paths = [p.strip() for p in paths_str.split(":") if p.strip()]
    if not paths:
        logger.error(
            "No paths specified. Set the MEDIA_PATHS environment variable "
            "or use the --paths argument."
        )
        sys.exit(1)

    trigger = parse_schedule(schedule_str)

    if trigger is None:
        # Single-shot mode
        logger.info("Running in single-shot mode.")
        exit_code = run_all_paths(paths, scan_only=scan_only, ignore_cache=ignore_cache)
        logger.info("Done.")
        sys.exit(exit_code)
    else:
        # Scheduled mode
        from apscheduler.schedulers.blocking import BlockingScheduler

        logger.info("Running in scheduled mode (schedule: %s).", schedule_str)
        scheduler = BlockingScheduler(timezone="UTC")
        scheduler.add_job(
            run_all_paths,
            trigger=trigger,
            args=[paths, scan_only, ignore_cache],
            misfire_grace_time=3600,
        )
        logger.info("Scheduler started. Press Ctrl+C to exit.")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
