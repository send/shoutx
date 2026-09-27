param([Parameter(Mandatory = $true)][string]$Binary)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion -lt [version]'7.4') {
    throw "PowerShell 7.4 or later is required"
}
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

    $empty = Join-Path $root 'empty-stdin'
    & $Binary github-actions:output empty > $empty
    if ($LASTEXITCODE -ne 0) { throw "empty-stdin writer failed" }
    $expectedEmpty = [Text.Encoding]::UTF8.GetBytes("empty=`n")
    if (-not [Linq.Enumerable]::SequenceEqual([byte[]](Get-Content -AsByteStream -Raw $empty), $expectedEmpty)) {
        throw "PowerShell did not pass inherited empty stdin through unchanged"
    }

    $rejectedBinary = Join-Path $root 'rejected-binary-stdin'
    & pwsh -NoProfile -Command `
        '[Console]::OpenStandardOutput().Write([byte[]](97,13,13,10))' |
        & $Binary github-actions:output result > $rejectedBinary
    if ($LASTEXITCODE -ne 1 -or (Get-Item $rejectedBinary).Length -ne 0) {
        throw "PowerShell did not preserve discriminating CR/CRLF stdin bytes"
    }

    $controlZ = Join-Path $root 'control-z-stdin'
    & pwsh -NoProfile -Command `
        '[Console]::OpenStandardOutput().Write([byte[]](97,26,98))' |
        & $Binary github-actions:output result > $controlZ
    if ($LASTEXITCODE -ne 0) { throw "control-Z stdin writer failed" }
    $expectedControlZ = [byte[]](114,101,115,117,108,116,61,97,26,98,10)
    if (-not [Linq.Enumerable]::SequenceEqual([byte[]](Get-Content -AsByteStream -Raw $controlZ), $expectedControlZ)) {
        throw "PowerShell treated control-Z as text or end-of-file"
    }

    $multiline = Join-Path $root 'multiline-bare-cr'
    & $Binary github-actions:output --multiline result "value`r" > $multiline
    if ($LASTEXITCODE -ne 0) { throw "multiline writer failed" }
    $multilineBytes = [byte[]](Get-Content -AsByteStream -Raw $multiline)
    $firstLf = [Array]::IndexOf($multilineBytes, [byte]10)
    if ($firstLf -lt 8) { throw "invalid multiline header" }
    $delimiter = [Text.Encoding]::UTF8.GetString($multilineBytes[8..($firstLf - 1)])
    $expectedMultiline = [Text.Encoding]::UTF8.GetBytes("result<<$delimiter`nvalue`r`r`n$delimiter`n")
    if (-not [Linq.Enumerable]::SequenceEqual($multilineBytes, $expectedMultiline)) {
        throw "PowerShell changed CR-sensitive multiline stdout bytes"
    }

    $pathOutput = Join-Path $root 'path'
    & $Binary github-actions:path 'C:\tools' > $pathOutput
    if ($LASTEXITCODE -ne 0) { throw "path writer failed" }
    $expectedPath = [Text.Encoding]::UTF8.GetBytes("C:\tools`n")
    if (-not [Linq.Enumerable]::SequenceEqual([byte[]](Get-Content -AsByteStream -Raw $pathOutput), $expectedPath)) {
        throw "PowerShell changed path stdout bytes"
    }
    & $Binary github-actions:path 'C:\bad;path' > (Join-Path $root 'rejected-path')
    if ($LASTEXITCODE -ne 1 -or (Get-Item (Join-Path $root 'rejected-path')).Length -ne 0) {
        throw "unsafe path was accepted"
    }

    $legacy = Join-Path $root 'legacy-powershell'
    & powershell.exe -NoProfile -Command `
        "& '$Binary' github-actions:output result value >> '$legacy'"
    if ($LASTEXITCODE -ne 0) { throw "Windows PowerShell fixture failed" }
    if ([Linq.Enumerable]::SequenceEqual([byte[]](Get-Content -AsByteStream -Raw $legacy), $expected)) {
        throw "Windows PowerShell unexpectedly preserved the native byte contract"
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
    $start = [Diagnostics.ProcessStartInfo]::new('pwsh')
    $start.UseShellExecute = $false
    foreach ($argument in @('-NoProfile', '-File', $child, $Binary, (Join-Path $root 'rejected'), $marker)) {
        $start.ArgumentList.Add($argument)
    }
    $process = [Diagnostics.Process]::Start($start)
    $process.WaitForExit()
    $childExit = $process.ExitCode
    if ($childExit -eq 0 -or (Test-Path $marker)) {
        throw "PowerShell did not propagate the rejected shoutx invocation"
    }
}
finally {
    Remove-Item -Recurse -Force $root
}
