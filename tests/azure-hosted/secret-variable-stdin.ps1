# Documentation helper, not a shipped command. Keep tracing off and acquire
# the credential as a byte stream without printing it or putting it in argv.
function Set-ShoutxSecretVariable {
    param(
        [Parameter(Mandatory)][string] $Binary,
        [Parameter(Mandatory)][System.IO.Stream] $InputStream,
        [Parameter(Mandatory)][string] $Name,
        [switch] $Output,
        [switch] $ReadOnly
    )
    $process = [System.Diagnostics.Process]::new()
    try {
        $process.StartInfo.FileName = $Binary
        $process.StartInfo.UseShellExecute = $false
        $process.StartInfo.RedirectStandardInput = $true
        # Inherit stdout/stderr directly; never capture the secret wire.
        $process.StartInfo.ArgumentList.Add('azure-pipelines:secret-variable')
        if ($Output) { $process.StartInfo.ArgumentList.Add('--output') }
        if ($ReadOnly) { $process.StartInfo.ArgumentList.Add('--read-only') }
        $process.StartInfo.ArgumentList.Add('--')
        $process.StartInfo.ArgumentList.Add($Name)
        if (-not $process.Start()) { throw 'Could not start secret assignment' }
        $InputStream.CopyTo($process.StandardInput.BaseStream)
        $process.StandardInput.BaseStream.Close()
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) { throw 'Secret assignment failed' }
    }
    catch {
        try {
            if (-not $process.HasExited) { $process.Kill(); $process.WaitForExit() }
        } catch { }
        throw 'Secret assignment failed; stop dependent work'
    }
    finally { $process.Dispose() }
}
