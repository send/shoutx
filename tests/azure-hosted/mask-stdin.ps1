# Documentation helper exercised by the hosted fixture, not a shipped command.
# The caller acquires the stream without printing secrets and keeps tracing off.
function Register-ShoutxMask {
    param(
        [Parameter(Mandatory)][string] $Binary,
        [Parameter(Mandatory)][System.IO.Stream] $InputStream,
        [switch] $EachLine
    )
    $process = [System.Diagnostics.Process]::new()
    try {
        $process.StartInfo.FileName = $Binary
        $process.StartInfo.UseShellExecute = $false
        $process.StartInfo.RedirectStandardInput = $true
        # stdout/stderr stay attached to the Agent, never captured as a value.
        $process.StartInfo.ArgumentList.Add('azure-pipelines:mask')
        if ($EachLine) { $process.StartInfo.ArgumentList.Add('--each-line') }
        if (-not $process.Start()) { throw 'Could not start mask registration' }
        # BaseStream bypasses StreamWriter's encoding/BOM/newline behavior.
        $InputStream.CopyTo($process.StandardInput.BaseStream)
        $process.StandardInput.BaseStream.Close()
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) { throw 'Mask registration failed' }
    }
    catch {
        try {
            if (-not $process.HasExited) { $process.Kill(); $process.WaitForExit() }
        } catch { }
        # Never relay exception text that might contain caller-controlled data.
        throw 'Mask registration failed; stop dependent work'
    }
    finally { $process.Dispose() }
}
