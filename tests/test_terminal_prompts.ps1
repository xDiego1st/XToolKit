#Requires -Version 5.1
# Offline functional regression tests for the numbered confirmation menu.
$ErrorActionPreference = "Stop"
$scriptFile = Join-Path $PSScriptRoot "../run-all.ps1"
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($scriptFile, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -gt 0) { throw "PowerShell syntax error" }
$fn = $ast.Find({
    param($node)
    ($node -is [System.Management.Automation.Language.FunctionDefinitionAst]) -and
    ($node.Name -eq "Confirm-Exact")
}, $true)
if ($null -eq $fn) { throw "Numeric confirmation function missing" }
Invoke-Expression $fn.Extent.Text
function Read-Host {
    param([string]$Prompt)
    return $script:TestInput
}
foreach ($row in @(
    @{ Value = "1"; Expected = $true },
    @{ Value = "2"; Expected = $false },
    @{ Value = "0"; Expected = $false },
    @{ Value = ""; Expected = $false },
    @{ Value = "VERIFIED"; Expected = $false },
    @{ Value = "RUN ALL"; Expected = $false },
    @{ Value = "bad"; Expected = $false }
)) {
    $script:TestInput = $row.Value
    $actual = Confirm-Exact -Prompt "Test prompt (no Google Play)" -Phrase "VERIFIED"
    if ($actual -ne $row.Expected) {
        throw ("Menu input '{0}' returned {1}, expected {2}" -f $row.Value, $actual, $row.Expected)
    }
}
Write-Host "Numbered confirmation menu tests: PASS" -ForegroundColor Green
