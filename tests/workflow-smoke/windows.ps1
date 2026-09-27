param([Parameter(Mandatory = $true)][string]$Binary)

$ErrorActionPreference = 'Stop'
$root = Join-Path ([System.IO.Path]::GetTempPath()) ("shoutx-smoke-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root | Out-Null
try {
    $single = Join-Path $root 'single'
    'value' | & $Binary github-actions:output result >> $single
    if ($LASTEXITCODE -ne 0) { throw "single-line writer failed" }
    $expected = [Text.Encoding]::UTF8.GetBytes("result=value`n")
    if (-not [Linq.Enumerable]::SequenceEqual([byte[]](Get-Content -AsByteStream -Raw $single), $expected)) {
        throw "PowerShell changed native stdout bytes"
    }

    foreach ($value in @('', '"quoted"', 'trailing\')) {
        $path = Join-Path $root ([guid]::NewGuid().ToString('N'))
        & $Binary github-actions:output result $value >> $path
        if ($LASTEXITCODE -ne 0) { throw "argv writer failed" }
        $expected = [Text.Encoding]::UTF8.GetBytes("result=$value`n")
        if (-not [Linq.Enumerable]::SequenceEqual([byte[]](Get-Content -AsByteStream -Raw $path), $expected)) {
            throw "PowerShell changed an argv value"
        }
    }

    $child = Join-Path $root 'propagate.ps1'
    $marker = Join-Path $root 'masked'
    @'
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
"a`nb" | & $args[0] github-actions:output result > $args[1]
New-Item -ItemType File -Path $args[2] | Out-Null
'@ | Set-Content -Encoding utf8NoBOM $child
    $previousNativePreference = $PSNativeCommandUseErrorActionPreference
    $PSNativeCommandUseErrorActionPreference = $false
    & pwsh -NoProfile -File $child $Binary (Join-Path $root 'rejected') $marker
    $childExit = $LASTEXITCODE
    $PSNativeCommandUseErrorActionPreference = $previousNativePreference
    if ($childExit -eq 0 -or (Test-Path $marker)) {
        throw "PowerShell did not propagate the rejected shoutx invocation"
    }
}
finally {
    Remove-Item -Recurse -Force $root
}
