#Requires -Version 5.1
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../scripts/user-errors.ps1")

$cases = @(
    @{ Code = "payment_security_blocked"; Needle = "OR-REH-04" },
    @{ Code = "already_subscribed"; Needle = "already active" },
    @{ Code = "ineligible"; Needle = "not eligible" },
    @{ Code = "today_price_unverified"; Needle = "due today" },
    @{ Code = "trial_duration_unverified"; Needle = "trial length" },
    @{ Code = "backup_payment_methods_prompt"; Needle = "backup payment methods" },
    @{ Code = "processing"; Needle = "still processing" },
    @{ Code = "subscribe_button_not_found"; Needle = "The checkout button was not found" },
    @{ Code = "offer_not_available"; Needle = "not available" },
    @{ Code = "offer_query_failed"; Needle = "Could not load" },
    @{ Code = "account_unavailable"; Needle = "Google Play account" },
    @{ Code = "device_missing"; Needle = "MuMu is not connected" },
    @{ Code = "launch_failed"; Needle = "Could not open Google Play checkout" },
    @{ Code = "billing_flow_error"; Needle = "Google Play could not open checkout" },
    @{ Code = "activity_lookup_failed"; Needle = "Could not access the Google One screen" },
    @{ Code = "add_account_failed"; Needle = "Could not add the Google account" },
    @{ Code = "add_account_error"; Needle = "Google account setup was interrupted" },
    @{ Code = "payment_method_not_confirmed"; Needle = "Could not verify the payment method" },
    @{ Code = "play_account_switch_failed"; Needle = "Could not switch Google Play accounts" },
    @{ Code = "account_unverified"; Needle = "Google Play account was not verified" },
    @{ Code = "wrong_account"; Needle = "Google Play is using the wrong account" },
    @{ Code = "frida_missing"; Needle = "Android instrumentation is not ready" },
    @{ Code = "environment_failed"; Needle = "Android environment check did not finish" },
    @{ Code = "confirmation_required"; Needle = "Approval is required to continue" }
)
foreach ($case in $cases) {
    $issue = Get-UserIssue -Code $case.Code
    if (-not $issue.Title.Contains($case.Needle)) {
        throw ("Incorrect title for {0}: {1}" -f $case.Code, $issue.Title)
    }
    if ([string]::IsNullOrWhiteSpace($issue.Action)) {
        throw ("Missing recommended action for {0}" -f $case.Code)
    }
}
$errors = @(
    @{ Message = "No online ADB devices"; Expected = "device_missing" },
    @{ Message = "Play account mismatch. Detected 'one@example.com', expected 'two@example.com'."; Expected = "account_mismatch" },
    @{ Message = "Cannot identify the active Google Play account. Open the Play Store profile."; Expected = "account_unavailable" },
    @{ Message = "Offer query did not complete: offer_query_failed"; Expected = "offer_query_failed" },
    @{ Message = "Offer query did not complete: app_not_started"; Expected = "app_not_started" },
    @{ Message = "Offer query did not complete: play_store_not_started"; Expected = "play_store_not_started" },
    @{ Message = "No report produced at ..." ; Expected = "report_missing" },
    @{ Message = "Python not found"; Expected = "python_missing" },
    @{ Message = "Invalid Play Store account returned by Step 1"; Expected = "account_unavailable" }
)
foreach ($case in $errors) {
    $actual = Get-FailureCode -ErrorMessage $case.Message
    if ($actual -cne $case.Expected) {
        throw ("Error map mismatch: {0} -> {1}" -f $case.Message, $actual)
    }
}
foreach ($code in @("app_not_started", "play_store_not_started")) {
    $action = (Get-UserIssue -Code $code).Action
    if ($action -notlike "*Close MuMu and reopen it*Check Device & Offers again from Step 1*") {
        throw "Missing MuMu restart guidance for $code"
    }
}
# User-facing mode must not reveal internal status codes in its output.
$compact = (Show-UserIssue -Code "trial_duration_unverified" 6>&1 | Out-String)
# Write-Host writes to the Information stream; use redirected host output
# when available while also testing that debug mode explicitly shows codes.
$source = Get-Content -LiteralPath (Join-Path $PSScriptRoot "../scripts/user-errors.ps1") -Raw
if (-not $source.Contains('if ($DebugMode)')) {
    throw "Raw error diagnostics must be conditional on debug mode."
}
# A missing Subscribe button must retain the payment-safety guidance
# and the helper must not have a duplicated/unreachable case.
$buttonIssue = Get-UserIssue -Code "subscribe_button_not_found"
foreach ($phrase in @("pricing", "subscriptions", "payment history", "No Subscribe action")) {
    if (-not $buttonIssue.Action.Contains($phrase)) {
        throw ("Missing checkout-button safety advice: {0}" -f $phrase)
    }
}
if (([regex]::Matches($source, '"subscribe_button_not_found"\s*\{')).Count -ne 1) {
    throw "Duplicate subscribe_button_not_found cases are not allowed"
}
# Interactive PowerShell must not print the private TUI marker.
$previousTuiMode = $env:EPLUS_TUI
try {
    Remove-Item Env:EPLUS_TUI -ErrorAction SilentlyContinue
    $plain = (Show-UserIssue -Code "launch_failed" 6>&1 | Out-String)
    if ($plain.Contains("EPLUS_ISSUE:launch_failed")) { throw "Raw protocol marker leaked to CLI" }
    if (-not $plain.Contains("Could not open Google Play checkout")) { throw "Missing friendly CLI error" }
    $env:EPLUS_TUI = "1"
    $machine = (Show-UserIssue -Code "launch_failed" 6>&1 | Out-String)
    if (-not $machine.Contains("EPLUS_ISSUE:launch_failed")) { throw "TUI protocol marker missing" }
} finally {
    if ($null -eq $previousTuiMode) {
        Remove-Item Env:EPLUS_TUI -ErrorAction SilentlyContinue
    } else {
        $env:EPLUS_TUI = $previousTuiMode
    }
}
Write-Host "Friendly error messages: PASS" -ForegroundColor Green
