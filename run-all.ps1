#Requires -Version 5.1
<#
.SYNOPSIS
  Single-entry Windows/MuMu setup, diagnostics, offer listing and optional guided stages.
.DESCRIPTION
  Defaults to the interactive Textual dashboard. Use -Cli or -Step 0..5 for the
  original command-line interface. Original Steps 2-5 require explicit selection.
  -AllStages runs original Steps 2-5, with approval for each billable stage.
  -StartStep 3 with -AllStages skips Step 2 when a subscription is already active.
  Individual -Step 2..5 commands do not require typed confirmations.
  -AllStages retains verification prompts between potentially billable steps.
  Step 5 is the author's optional additional offer and can be skipped.
  The original ultra0.py may automatically click Subscribe during a live stage.
  Always verify the account, current charge, renewal terms and subscription in Google Play.
.EXAMPLE
  .\run-all.ps1                       # Textual dashboard, installs UI dependency if missing
.EXAMPLE
  .\run-all.ps1 -Cli                  # Legacy CLI mode, read-only Step 1
.EXAMPLE
  .\run-all.ps1 -Step 0               # Original environment check
.EXAMPLE
  .\run-all.ps1 -Step 1               # Original read-only offer list (default)
.EXAMPLE
  .\run-all.ps1 -Step 2 -Email account@example.com  # No typed confirmation; may purchase
.EXAMPLE
  .\run-all.ps1 -Step 5 -Email account@example.com
.EXAMPLE
  .\run-all.ps1 -AllStages                       # Original steps 2-5, with confirmation
.EXAMPLE
  .\run-all.ps1 -AllStages -Force                # Author's account-check bypass (unsafe)
.EXAMPLE
  .\run-all.ps1 -AllStages -StartStep 3         # Resume without replaying Step 2
#>
[CmdletBinding()]
param(
    [string]$Email = "",
    [string]$Serial = "",
    [ValidateRange(0,4)]
    [int]$Step = 1,
    [switch]$AllStages,
    [ValidateRange(2,4)]
    [int]$StartStep = 2,
    [switch]$Force,
    [ValidateSet("auto", "choose", "thread")]
    [string]$ActivityMethod = "auto",
    [switch]$SetupOnly,
    [switch]$ListOnly,
    [switch]$Reinject,
    [switch]$Tui,
    [switch]$Cli,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
# Python stdout is piped into Windows PowerShell in Run-Command. Without a
# UTF-8 child stream, non-ASCII status symbols (e.g. ✓ / ✅) raise
# UnicodeEncodeError on Windows locales such as cp1252.
# Set the encoding BEFORE any Python subprocess, for both CLI and TUI paths.
$env:PYTHONIOENCODING = "utf-8:backslashreplace"
$env:PYTHONUTF8 = "1"
$utf8Output = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = $utf8Output
try {
    [Console]::OutputEncoding = $utf8Output
} catch {
    # Some non-interactive PowerShell hosts do not expose Console.OutputEncoding.
    # The child process still uses UTF-8; avoid failing before preflight.
}
# -Debug is a built-in PowerShell common parameter when CmdletBinding is used.
# Do not declare a second Debug switch; simply read its caller-supplied value.
$ShowDebug = $PSBoundParameters.ContainsKey("Debug") -and [bool]$PSBoundParameters["Debug"]
. (Join-Path $PSScriptRoot "scripts/user-errors.ps1")

function Show-Banner {
    Write-Host ""
    Write-Host "  ✦ XToolKit-Diego" -ForegroundColor Cyan
    $mode = if ($AllStages) { "Semua tahap, mulai Step $StartStep" } else { "Step $Step" }
    Write-Host ("  {0}" -f $mode) -ForegroundColor Gray
}
function Stage([string]$Message) {
    if ($ShowDebug -or $Message -match '^Original Step [2-5]:' -or
        $Message -eq "Original Step 1: List Google AI Pro offers") {
        $title = $Message -replace '^Original ', '' -replace ': List Google AI Pro offers$', ': Offers'
        Write-Host ""
        Write-Host ("  > {0}" -f $title) -ForegroundColor Cyan
    }
}
function Note([string]$Message) {
    if ($ShowDebug) { Write-Host ("    {0}" -f $Message) -ForegroundColor DarkGray }
}
function Show-Status([string]$Label, [string]$Value, [string]$Color = "Green") {
    Write-Host ("  {0,-11} " -f $Label) -NoNewline -ForegroundColor Gray
    Write-Host $Value -ForegroundColor $Color
}
function Stop-Workflow([string]$Reason) {
    throw $Reason
}
function Run-Command([string]$Program, [string[]]$Arguments) {
    # Preserve real-time output for Android manual verification, but hide
    # routine Python/ADB diagnostics. All stdout remains in a local ignored log.
    & $Program @Arguments | ForEach-Object {
        $line = [string]$_
        if ($script:RunLog) { Add-Content -LiteralPath $script:RunLog -Value $line -Encoding UTF8 }
        if ($ShowDebug) {
            Write-Host $line -ForegroundColor DarkGray
        } elseif ($line -match 'Action required:|Press Enter to continue') {
            Write-Host ("    {0}" -f $line.Trim()) -ForegroundColor Yellow
        }
    }
    if ($LASTEXITCODE -ne 0) {
        Stop-Workflow ("A tool failed (exit {0}). See local run log; do not retry checkout blindly." -f $LASTEXITCODE)
    }
}
function Get-RuntimeValue([string[]]$LookupArgs) {
    $output = @(& $Python "scripts/runtime-lookup.py" @LookupArgs)
    if ($LASTEXITCODE -ne 0) {
        Stop-Workflow "Runtime lookup failed. Verify the Python and ADB environment."
    }
    $resultLine = $output | Where-Object { $_ -match '^RUNTIME_RESULT:[A-Za-z0-9+/=]*$' } | Select-Object -Last 1
    if ($null -eq $resultLine) {
        Stop-Workflow "No machine-readable runtime result was returned."
    }
    $encoded = ([string]$resultLine).Substring("RUNTIME_RESULT:".Length)
    return [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encoded))
}

function Get-AccountReportKey([string]$Email) {
    $normalized = $Email.Trim().ToLowerInvariant()
    if ($normalized -eq "current@device") { return "current" }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($normalized))
        return "account-" + [System.BitConverter]::ToString($digest).Replace("-", "").ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Read-PythonReport([string]$AccountKey) {
    $reportFile = Join-Path $PSScriptRoot ("ultra0-report\{0}.json" -f $AccountKey)
    if (-not (Test-Path -LiteralPath $reportFile)) {
        Stop-Workflow "No report produced at $reportFile"
    }
    return (Get-Content -LiteralPath $reportFile -Raw -Encoding UTF8 | ConvertFrom-Json)
}
function Confirm-Exact([string]$Prompt, [string]$Phrase) {
    Write-Host ""
    Write-Host ("  ?  {0}" -f $Prompt) -ForegroundColor Yellow
    Write-Host "     [1] Lanjutkan" -ForegroundColor Green
    Write-Host "     [2] Lewati / Akhiri" -ForegroundColor Yellow
    Write-Host "     [0] Berhenti" -ForegroundColor DarkGray
    $answer = Read-Host "     Pilih 1/2/0"
    if ($null -eq $answer) { return $false }
    if ($answer.Trim() -eq "1") { return $true }
    if ($answer.Trim() -notin @("0", "2")) {
        Write-Host "     Pilihan tidak valid; berhenti dengan aman." -ForegroundColor Yellow
    }
    return $false
}

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Detailed
    exit 0
}
if ($AllStages -and $PSBoundParameters.ContainsKey("Step") -and $Step -ne 1) {
    Stop-Workflow "Choose either -AllStages or -Step 0..5, not both."
}
if ($PSBoundParameters.ContainsKey("StartStep") -and -not $AllStages) {
    Stop-Workflow "-StartStep requires -AllStages."
}

# The no-argument entrypoint is the interactive dashboard. Explicit -Step,
# -AllStages and -Cli preserve the original command-line behavior.
if ($Tui -and $Cli) {
    Stop-Workflow "Choose -Tui or -Cli, not both."
}
$useTui = $Tui -or (-not $Cli -and -not $PSBoundParameters.ContainsKey("Step") -and
                   -not $AllStages -and -not $SetupOnly -and -not $ListOnly -and -not $Help)
if ($useTui) {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Error "Python is required for the terminal interface."
        exit 1
    }
    $pythonPath = (Get-Command python -ErrorAction Stop).Source
    $textualInstalled = & $pythonPath -c "import importlib.util; print('1' if importlib.util.find_spec('textual') else '0')"
    if ($textualInstalled -ne "1") {
        Write-Host "Installing Textual for the terminal interface..." -ForegroundColor Cyan
        & $pythonPath -m pip install --disable-pip-version-check -r (Join-Path $PSScriptRoot "requirements-tui.txt")
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Unable to install Textual. Try: python -m pip install -r requirements-tui.txt"
            exit 1
        }
    }
    $tuiArgs = @((Join-Path $PSScriptRoot "tui.py"), "--step", [string]$(if ($AllStages) { $StartStep } else { $Step }))
    if ($AllStages) { $tuiArgs += "--sequence" }
    if ($ShowDebug) { $tuiArgs += "--debug" }
    & $pythonPath @tuiArgs
    exit $LASTEXITCODE
}
$startedAt = Get-Date
Push-Location $PSScriptRoot
try {
    Show-Banner
    $logDir = Join-Path $PSScriptRoot "logs"
    if (-not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    $script:RunLog = Join-Path $logDir ("run-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss-fff"))
    Stage "Preflight: Python and Android tools"
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Stop-Workflow "Python not found. Install Python 3.10+ from python.org, reopen PowerShell, then retry."
    }
    $Python = (Get-Command python -ErrorAction Stop).Source
    Run-Command $Python @("--version")

    $adbCommand = Get-Command adb -ErrorAction SilentlyContinue
    $Adb = if ($adbCommand) { $adbCommand.Source } else { "" }
    if (-not $Adb) {
        Note "ADB is not on PATH. Locating an existing ADB or installing platform-tools."
        $Adb = Get-RuntimeValue -LookupArgs @("adb")
    }
    if (-not $Adb) {
        Stop-Workflow "adb.exe was not found. Install Android SDK platform-tools or configure PATH and retry."
    }
    $env:ADB_PATH = $Adb
    Run-Command $Adb @("version")

    Stage "Preflight: Identify Android device"
    $deviceLines = @(& $Adb devices)
    if ($LASTEXITCODE -ne 0) { Stop-Workflow "ADB device discovery failed." }
    $online = @(
        foreach ($line in $deviceLines) {
            if ($line -match '^\s*(\S+)\s+device\s*$') { $Matches[1] }
        }
    )
    if ($online.Count -eq 0) {
        Show-Status "Connection" "Trying local emulator ADB ports..."
        $null = Get-RuntimeValue -LookupArgs @("connect-device")
        $deviceLines = @(& $Adb devices)
        if ($LASTEXITCODE -ne 0) { Stop-Workflow "ADB device discovery failed after reconnect." }
        $online = @(
            foreach ($line in $deviceLines) {
                if ($line -match '^\s*(\S+)\s+device\s*$') { $Matches[1] }
            }
        )
    }
    if ($online.Count -eq 0) {
        Note ($deviceLines -join [Environment]::NewLine)
        Stop-Workflow "No online ADB devices. Start MuMu, enable ADB debugging and wait for status 'device'."
    }
    if ($Serial) {
        if ($online -cnotcontains $Serial) {
            Stop-Workflow ("Selected serial '{0}' not online. Online: {1}" -f $Serial, ($online -join ", "))
        }
    } elseif ($online.Count -eq 1) {
        $Serial = $online[0]
    } else {
        Note ("Multiple ADB connections: {0}" -f ($online -join ", "))
        Note "Identifying duplicate transports and checking Google One..."
        $candidate = Get-RuntimeValue -LookupArgs @("device")
        if ($candidate -and $online -ccontains $candidate) {
            $Serial = $candidate
            Note ("Auto-selected Android device: {0}" -f $Serial)
        } else {
            Note "Multiple different devices are still eligible; explicit selection is required."
            if (-not $AllStages) {
                Stop-Workflow "Cannot select a single Android device automatically. Rerun with -Serial <exact-adb-serial>; no checkout started."
            }
            for ($i = 0; $i -lt $online.Count; $i++) {
                Note ("[{0}] {1}" -f ($i + 1), $online[$i])
            }
            $deviceAnswer = Read-Host "  Device number (0 to stop)"
            $deviceNumber = 0
            if (-not [int]::TryParse($deviceAnswer, [ref]$deviceNumber) -or
                $deviceNumber -lt 1 -or $deviceNumber -gt $online.Count) {
                Stop-Workflow "Invalid device number; no checkout started."
            }
            $Serial = $online[$deviceNumber - 1]
        }
    }
    Show-Status "Device" $Serial
    $AndroidVersion = ((& $Adb -s $Serial shell getprop ro.build.version.release) | Out-String).Trim()
    $AndroidSdk = ((& $Adb -s $Serial shell getprop ro.build.version.sdk) | Out-String).Trim()
    $AndroidAbi = ((& $Adb -s $Serial shell getprop ro.product.cpu.abi) | Out-String).Trim()
    if ($AndroidVersion -and $AndroidSdk -and $AndroidAbi) {
        Show-Status "Android" ("{0} (SDK {1}), ABI {2}" -f $AndroidVersion, $AndroidSdk, $AndroidAbi)
    }
    Note ("Activity lookup: {0}" -f $ActivityMethod)

    Stage "Preflight: Verify required Android apps"
    foreach ($package in @("com.android.vending", "com.google.android.apps.subscriptions.red")) {
        $apk = ((& $Adb -s $Serial shell pm path $package) | Out-String).Trim()
        if ($apk -notmatch 'package:') {
            Stop-Workflow ("Android package missing or disabled: {0}. Install/enable it in MuMu." -f $package)
        }
        Note ("Installed: {0}" -f $package)
    }

    Stage "Original Step 0: Environment check"
    Note "The original ultra0.py may repair Frida and change emulator proxy/network settings."
    Run-Command $Python @("ultra0.py", "--check", "--serial", $Serial)
    Write-Host "EPLUS_STAGE_DONE:0"

    if ($SetupOnly -or ($Step -eq 0 -and -not $AllStages)) {
        Note "Original Step 0 complete. No checkout or purchase requested."
        return
    }

    Stage "Preflight: Read active Google Play account"
    $playAccount = (Get-RuntimeValue -LookupArgs @("play-account", "--serial", $Serial)).Trim().ToLowerInvariant()
    if ($playAccount) { Show-Status "Account" $playAccount }
    else { Note "Play account lookup incomplete; retrying through the offer listing." }

    Stage "Original Step 1: List Google AI Pro offers"
    # The script's --list mode only queries product details; it does not call launchBillingFlow.
    Run-Command $Python @("ultra0.py", "--account", "current@device", "--no-add",
                            "--list", "--plan", "pro12", "--serial", $Serial,
                            "--activity-method", $ActivityMethod)
    $offerReport = Read-PythonReport "current"
    if ($offerReport.status -ne "listed") {
        Stop-Workflow ("Offer query did not complete: {0}" -f $offerReport.status)
    }

    # Reuse the Play account that ultra0.py already verified during Step 1.
    # If preflight and listing disagree, abort instead of choosing an account.
    $listedAccount = ""
    if ($offerReport.PSObject.Properties.Name -contains "detected_play_account") {
        $listedAccount = ([string]$offerReport.detected_play_account).Trim().ToLowerInvariant()
    }
    if ($listedAccount -and $listedAccount -notmatch '^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$') {
        Stop-Workflow "Invalid Play Store account returned by Step 1. Verify the Play Store profile."
    }
    if ($playAccount -and $listedAccount -and $playAccount -cne $listedAccount) {
        $accountMismatch = ("Play Store account changed: preflight '{0}', Step 1 '{1}'. " +
                            "Verify the Play Store profile before any checkout.")
        Stop-Workflow ($accountMismatch -f $playAccount, $listedAccount)
    }
    if (-not $playAccount -and $listedAccount) {
        $playAccount = $listedAccount
        Show-Status "Account" $playAccount
    }
    Show-Status "Offers" ("{0} found" -f @($offerReport.offers).Count)
    if ($ShowDebug -or ($Step -eq 1 -and -not $AllStages)) {
        foreach ($offer in @($offerReport.offers)) {
            $firstPhase = if ([string]$offer.micros -eq "0") { "0 (first phase)" } else { "Paid (first phase)" }
            Write-Host ("    {0,-25} {1,-6} {2}" -f [string]$offer.id, [string]$offer.period, $firstPhase) -ForegroundColor Gray
        }
    }

    # The Activity probe is diagnostic only. It is not a precondition for
    # launchBillingFlow, so run it only when detailed diagnostics are requested.
    if ($ShowDebug) {
        Stage "Diagnostic: Read-only Android Activity inspection"
        $googleOnePid = ((& $Adb -s $Serial shell pidof com.google.android.apps.subscriptions.red) | Out-String).Trim()
        if ($googleOnePid -match '^\d+$') {
            & $Python "scripts/diagnose-activity.py" "--serial" $Serial
            if ($LASTEXITCODE -ne 0) { Write-Warning "Optional Activity probe failed." }
        } else {
            Write-Warning "Google One is not running for the optional Activity probe."
        }
    }
    if ($ListOnly -or ($Step -eq 1 -and -not $AllStages)) {
        Note "Original Step 1 complete. No checkout or purchase requested."
        return
    }

    Stage "Optional original Pro subscription steps (2-5)"
    Note "CAUTION: ultra0.py is not a harmless preview. It can automatically press Subscribe."
    Note "An offer with micros=0 may still have later paid phases, and stacking 12+6+6 months is UNVERIFIED."
    if ($AllStages) {
        Note "Choose: 1 = Continue | 2 = Skip | 0 = Stop."
    } else {
        Note "Single-step mode: no console confirmations; the selected step may open and confirm a Google Play checkout."
    }

    # Reuse the selected Play account. No repeated email input is required.
    if (-not $Email -and $playAccount) {
        $Email = $playAccount
        Note ("Using detected Google Play account: {0}" -f $Email)
    }
    if (-not $Email -and $Force) {
        # Mirrors the author's --account current@device --force when profile
        # enumeration is unavailable. No additional account is added.
        $Email = "current@device"
    }
    if (-not $Email) {
        if (-not $AllStages) {
            Stop-Workflow "Cannot identify the active Google Play account. Rerun with -Email <account-email>; no checkout started."
        }
        $Email = Read-Host "Google Play email (Enter to stop)"
    }
    $Email = $Email.Trim().ToLowerInvariant()
    if ($Email -ne "current@device" -and $Email -notmatch '^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$') {
        Note "No valid email supplied; stopping before live billing."
        return
    }
    if ($Force) {
        Write-Warning "--force bypasses only the Play Store account check, NOT Google's eligibility or payment conditions."
        Write-Warning ("Detected Play account: {0}; requested: {1}" -f $playAccount, $Email)
        if ($AllStages) {
            if (-not (Confirm-Exact "Use original --force for this Android account?" "FORCE")) {
                return
            }
        } else {
            Note "The -Force switch was explicitly supplied; no additional console confirmation in single-step mode."
        }
    } elseif (-not $playAccount) {
        # An unreadable account is not proof that the wrong account is active.
        # Never guess or bypass this identity check on a paid stage.
        Stop-Workflow "Cannot identify the active Google Play account. Open the Play Store profile, select the intended account, then repeat Step 1."
    } elseif ($playAccount -cne $Email) {
        $accountMismatch = ("Play account mismatch. Detected '{0}', expected '{1}'. " +
                            "Select the correct Play Store account and repeat Step 1.")
        Stop-Workflow ($accountMismatch -f $playAccount, $Email)
    }

    # Keep the original author's Pro 5 TB stage numbering and plan IDs.
    # Step 5 is the author's optional additional offer and requires explicit approval.
    $stages = @(
        [pscustomobject]@{ Number = 2; Name = "Pro 12-month offer"; Plan = "pro12"; Offer = "12months-eft"; Stack = $false },
        [pscustomobject]@{ Number = 3; Name = "Pro additional 6 months"; Plan = "pro6"; Offer = "6months-eft"; Stack = $true },
        [pscustomobject]@{ Number = 4; Name = "Pro second additional 6 months"; Plan = "pro6b"; Offer = "6months-eft-2"; Stack = $true }
    )
    $selectedStages = @(
        if ($AllStages) {
            $stages | Where-Object { $_.Number -ge $StartStep -and $_.Number -le 4 }
        } else {
            $stages | Where-Object { $_.Number -eq $Step }
        }
    )
    if ($AllStages) {
        Note ("The original sequence will start at Step {0} and may initiate real Google Play transactions." -f $StartStep)
        if ($StartStep -gt 2) {
            Note ("Skipping Steps 2-{0}; previous subscription extensions cannot be verified automatically." -f ($StartStep - 1))
            if (-not (Confirm-Exact "Confirm Google Play shows an ACTIVE Google AI Pro subscription and review its next charge date" "ACTIVE")) {
                return
            }
        }
        if (-not (Confirm-Exact ("Run original stages starting at Step {0}, including optional Step 5?" -f $StartStep) "RUN ALL")) {
            return
        }
    }
    $key = Get-AccountReportKey $Email
    foreach ($stage in $selectedStages) {
        Stage ("Original Step {0}: {1}" -f $stage.Number, $stage.Name)
        Show-Status "Offer" $stage.Offer "Cyan"

        # Recheck offer metadata before each transaction, not just once at
        # the beginning of a potentially long multi-step workflow.
        if ($stage.Number -ne 2 -or $AllStages) {
            Run-Command $Python @("ultra0.py", "--account", "current@device", "--no-add",
                                  "--list", "--plan", $stage.Plan, "--serial", $Serial,
                                  "--activity-method", $ActivityMethod)
            $offerReport = Read-PythonReport "current"
            if ($offerReport.status -ne "listed") {
                Stop-Workflow ("Could not refresh the offer list for Step {0}: {1}" -f $stage.Number, $offerReport.status)
            }
        }
        $available = @($offerReport.offers | Where-Object { $_.id -eq $stage.Offer -and [string]$_.micros -eq "0" })
        if ($available.Count -eq 0) {
            Show-UserIssue -Code "offer_not_available" -Details ("Step {0}, offer {1}" -f $stage.Number, $stage.Offer) -DebugMode $ShowDebug
            break
        }

        if ($stage.Stack) {
            Note "The original author requires an existing ACTIVE subscription for an update."
            Note "Do not proceed if the prior subscription was cancelled, expired or not verified."
        } else {
            Note "Step 2 is ONLY for accounts with no active Google One subscription."
            if ($AllStages) {
                if (-not (Confirm-Exact "Confirm Google Play shows NO ACTIVE Google One subscription for this account" "NO ACTIVE")) {
                    Note "Skipping Step 2. For an existing plan, resume with -AllStages -StartStep 3 only after checking Google Play."
                    break
                }
            } else {
                Note "Single-step mode: you selected Step 2 explicitly. Google Play must reject duplicate or ineligible subscriptions."
            }
        }
        Note "Inspect today's checkout price, all future pricing phases and the next charge date."
        Note "A 0-price first phase is NOT proof of free-trial eligibility or stacking."
        # Approve the main sequence once. Step 5 stays optional,
        # and a standalone -Step N run still requires explicit permission.
        if ($AllStages -and $stage.Number -eq 5) {
            if (-not (Confirm-Exact "Run this optional original live stage?" "RUN 5")) { break }
        }

        $args = @("ultra0.py", "--account", $Email, "--no-add", "--no-switch",
                  "--plan", $stage.Plan, "--serial", $Serial, "--activity-method", $ActivityMethod)
        if ($stage.Number -ge 2) { $args += "--open-only" }
        if ($Force) { $args += "--force" }
        if ($stage.Stack) { $args += "--stack" }
        Run-Command $Python $args

        $report = Read-PythonReport $key
        $reason = ""
        if ($report.PSObject.Properties.Name -contains "sheet" -and $null -ne $report.sheet) {
            if ($report.sheet.PSObject.Properties.Name -contains "reason") {
                $reason = [string]$report.sheet.reason
            }
        }
        if ($report.status -eq "billing_opened") {
            Show-Status "Billing" "Google Play Billing terbuka; lanjutkan pembayaran di Android" "Green"
        } elseif ($report.status -eq "checkout_requested") {
            Show-Status "Checkout" "Submitted; check Google Play" "Yellow"
        } else {
            $issueCode = if ($reason) { $reason } else { [string]$report.status }
            $issueDetails = ""
            if ($report.PSObject.Properties.Name -contains "error") {
                $issueDetails = [string]$report.error
            }
            Show-UserIssue -Code $issueCode -Details $issueDetails -DebugMode $ShowDebug
            break
        }

        Write-Host "  Check the actual renewal date in Google Play." -ForegroundColor Yellow
        if ($AllStages) {
            if (-not (Confirm-Exact "Only if you verified the active plan, renewal date and future price in Google Play, continue?" "VERIFIED")) {
                break
            }
        } else {
            Note "Single step finished. Review the actual subscription and renewal date in Google Play."
        }
    }

    if ($ShowDebug) { Note ("Local diagnostics: {0}" -f $script:RunLog) }
}
catch {
    $rawError = [string]$_.Exception.Message
    $issueCode = Get-FailureCode -ErrorMessage $rawError
    Show-UserIssue -Code $issueCode -Details $rawError -DebugMode $ShowDebug
    if ($ShowDebug -and $script:RunLog) {
        Write-Host ("    Log: {0}" -f $script:RunLog) -ForegroundColor DarkGray
    }
    exit 1
}
finally {
    Pop-Location
}
