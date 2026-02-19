# fix-single-chapters.ps1
# Removes chapter metadata from MP4 files that have only 1 chapter

param(
    [Parameter(Mandatory=$true)]
    [string]$Path,

    [switch]$ScanOnly,
    [switch]$IgnoreCache
)

$checkedFilesPath = Join-Path -Path $Path -ChildPath "checked-files.txt"
$problemFilesPath = Join-Path -Path $Path -ChildPath "single-chapter-files.txt"

# Log ffmpeg version
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    $ffmpegVersionLine = (ffmpeg -version 2>&1 | Select-Object -First 1) -as [string]
    if ($ffmpegVersionLine -match '^ffmpeg version (\S+)') {
        Write-Host "ffmpeg version: $($Matches[1])" -ForegroundColor Cyan
    } else {
        Write-Host "ffmpeg version: $ffmpegVersionLine" -ForegroundColor Cyan
    }
} else {
    Write-Host "ffmpeg not found — ensure it is installed and on PATH" -ForegroundColor Red
}

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

# Load previously checked files
$checkedFiles = @{}
if ((Test-Path $checkedFilesPath) -and -not $IgnoreCache) {
    Get-Content $checkedFilesPath | ForEach-Object {
        $checkedFiles[$_] = $true
    }
    Write-Host "Loaded $($checkedFiles.Count) previously checked file(s) from cache" -ForegroundColor Cyan
}

$problemFiles = @()
$fixedFiles = @()
$newlyChecked = @()
$skippedCount = 0
$checkedCount = 0

Get-ChildItem -Path $Path -Filter "*.mp4" -Recurse | ForEach-Object {
    $file = $_.FullName

    # Skip if already checked
    if ($checkedFiles.ContainsKey($file)) {
        $skippedCount++
        return
    }

    Write-Host "Checking: $file"

    # Get chapter count using ffprobe
    $chapterCount = (ffprobe -v quiet -print_format json -show_chapters "$file" |
                     ConvertFrom-Json).chapters.Count

    $checkedCount++

    if ($chapterCount -eq 1) {
        if ($ScanOnly) {
            Write-Host "  Single chapter found" -ForegroundColor Yellow
            $problemFiles += $file
            # Do not cache — file hasn't been fixed; allow it to be caught on a future fix run
        } else {
            Write-Host "  Fixing..."

            $tempFile = "$file.tmp.mp4"

            # Remove chapters without re-encoding
            ffmpeg -i "$file" -map_chapters -1 -c copy "$tempFile" -y -loglevel warning

            if ($LASTEXITCODE -eq 0) {
                Remove-Item "$file" -Force
                Rename-Item "$tempFile" "$file"
                Write-Host "  Done!" -ForegroundColor Green
                $fixedFiles += $file
                $newlyChecked += $file
            } else {
                Remove-Item "$tempFile" -ErrorAction SilentlyContinue
                Write-Host "  Failed!" -ForegroundColor Red
                $problemFiles += $file
                # Do not cache — fix failed; allow retry on next run
            }
        }
    } else {
        Write-Host "  OK ($chapterCount chapters)" -ForegroundColor DarkGray
        $newlyChecked += $file
    }
}

# Update checked files cache — only when new files were cleared for caching
if ($newlyChecked.Count -gt 0) {
    $allChecked = @($checkedFiles.Keys) + $newlyChecked
    $allChecked | Out-File -FilePath $checkedFilesPath -Encoding UTF8
}

# Combine problem and fixed files for reporting
$allProblemFiles = $problemFiles + $fixedFiles

# Always write problem files list if any were found
if ($allProblemFiles.Count -gt 0) {
    $allProblemFiles | Out-File -FilePath $problemFilesPath -Encoding UTF8
}

# Summary
Write-Host "`n--- Summary ---" -ForegroundColor Cyan
Write-Host "Skipped (cached):  $skippedCount"
Write-Host "Checked (new):     $checkedCount"
Write-Host "Problems found:    $($allProblemFiles.Count)"

if (-not $ScanOnly -and $fixedFiles.Count -gt 0) {
    Write-Host "  - Fixed:         $($fixedFiles.Count)" -ForegroundColor Green
}
if ($problemFiles.Count -gt 0) {
    $label = if ($ScanOnly) { "  - Pending:" } else { "  - Failed:" }
    Write-Host "$label        $($problemFiles.Count)" -ForegroundColor Yellow
}

if ($allProblemFiles.Count -gt 0) {
    Write-Host "Results saved to:  $problemFilesPath" -ForegroundColor Cyan
}
if ($newlyChecked.Count -gt 0) {
    Write-Host "Cache saved to:    $checkedFilesPath" -ForegroundColor Cyan
}
$stopwatch.Stop()
Write-Host "Duration:          $([math]::Round($stopwatch.Elapsed.TotalSeconds, 1))s"
