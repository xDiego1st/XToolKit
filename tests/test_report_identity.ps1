#Requires -Version 5.1
# Verify that PowerShell and Python select the same report for each full email.
$ErrorActionPreference = "Stop"
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $PSScriptRoot "../run-all.ps1"),
    [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -gt 0) { throw "Invalid PowerShell wrapper" }
$functionAst = $ast.Find({
    param($node)
    ($node -is [System.Management.Automation.Language.FunctionDefinitionAst]) -and
    ($node.Name -eq "Get-AccountReportKey")
}, $true)
if (-not $functionAst) { throw "Report key helper is missing" }
Invoke-Expression $functionAst.Extent.Text

foreach ($account in @("alice@gmail.com", "ALICE@GMAIL.COM", "alice@yahoo.com", "current@device")) {
    $actual = (Get-AccountReportKey $account) + ".json"
    $expected = (& python -c "import ultra0; print(ultra0.report_filename('$account'))").Trim()
    if ($LASTEXITCODE -ne 0 -or $actual -cne $expected) {
        throw "Report key mismatch for $account"
    }
}
if ((Get-AccountReportKey "alice@gmail.com") -eq (Get-AccountReportKey "alice@yahoo.com")) {
    throw "Different Google accounts must not overwrite the same report"
}
Write-Host "Full-account report identity checks: PASS"
