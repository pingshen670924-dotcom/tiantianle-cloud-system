param(
  [switch]$HistoryOnly,
  [switch]$NetworkOnly,
  [switch]$ValidateOnly,
  [switch]$All,
  [switch]$NoOpen
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir
$GrabberDirName = -join @([char]0x6293, [char]0x53D6, [char]0x5668)
$DailyGrabberDirName = -join @([char]0x5929, [char]0x5929, [char]0x6A02, [char]0x6293, [char]0x53D6, [char]0x5668)
$UserSelectedCsv = Join-Path ([Environment]::GetFolderPath("Desktop")) (Join-Path $GrabberDirName (Join-Path $DailyGrabberDirName "fantasy5_full_history.csv"))
$HistoryDir = Join-Path $ScriptDir "history_import"
New-Item -ItemType Directory -Force -Path $HistoryDir | Out-Null
if (Test-Path -LiteralPath $UserSelectedCsv) {
  Copy-Item -LiteralPath $UserSelectedCsv -Destination (Join-Path $HistoryDir "00_user_selected_fantasy5_full_history.csv") -Force
}
$CacheDir = Join-Path $ScriptDir "data\latest_cache"
New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null

$LatestPages = @(
  @{ Name = "lotto8_latest.html"; Url = "https://www.lotto-8.com/usa/listltoFT5.asp?indexpage=1&orderby=new" },
  @{ Name = "lottolyzer_latest.html"; Url = "https://en.lottolyzer.com/history/united-states/fantasy-5-california/" },
  @{ Name = "lotteryusa_latest.html"; Url = "https://www.lotteryusa.com/california/fantasy-5/" },
  @{ Name = "lotterynet_latest.html"; Url = "https://www.lottery.net/california/fantasy-5/numbers" },
  @{ Name = "lotterynet_year.html"; Url = "https://www.lottery.net/california/fantasy-5/numbers/$((Get-Date).Year)" }
)
foreach ($Page in $LatestPages) {
  try {
    Invoke-WebRequest -Uri $Page.Url -UseBasicParsing -TimeoutSec 15 -OutFile (Join-Path $CacheDir $Page.Name)
  } catch {
    Write-Warning "Latest page download failed: $($Page.Url)"
  }
}

$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$PythonCommand = "python"
if (-not (Get-Command $PythonCommand -ErrorAction SilentlyContinue)) {
  if (Test-Path $BundledPython) {
    $PythonCommand = $BundledPython
  } else {
    throw "Python executable was not found."
  }
}

$ArgsList = @(".\california_fantasy5_system.py")
if ($HistoryOnly) {
  $ArgsList += "--history-only"
}
if ($NetworkOnly) {
  $ArgsList += "--network-only"
}
if ($ValidateOnly) {
  $ArgsList += "--validate-only"
}
if ($All) {
  $ArgsList += "--all"
}

& $PythonCommand @ArgsList
if (-not $NoOpen) {
  if ($ValidateOnly) {
    Start-Process (Join-Path $ScriptDir "reports\source_validation_report.md")
  } elseif ($NetworkOnly) {
    Start-Process (Join-Path $ScriptDir "reports\network_diagnostic_report.md")
  } elseif ($HistoryOnly) {
    Start-Process (Join-Path $ScriptDir "reports\history_scraper_report.md")
  } else {
    Start-Process (Join-Path $ScriptDir "site\index.html")
  }
}
