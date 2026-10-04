using System.Text.Json;
using GitHub.Runner.Sdk;

// Exercises the published SDK invoker, not a registered/live Worker. The parent
// selectors must already be absent; only the Python child's overlay is changed.
static class EnvironmentTransportProbe
{
    public static object? CurrentCase;
    static readonly string[] Keys = [
        "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT", "DOTNET_SYSTEM_GLOBALIZATION_USENLS",
        "DOTNET_SYSTEM_GLOBALIZATION_APPLOCALICU", "DOTNET_SYSTEM_GLOBALIZATION_PREDEFINED_CULTURES_ONLY",
        "CLR_ICU_VERSION_OVERRIDE", "ICU_DATA"];
    const string Control = "SHOUTX_TRANSPORT_INHERITANCE_CONTROL";
    sealed class QuietTrace : ITraceWriter
    {
        public void Info(string message) { }
        public void Verbose(string message) { }
    }

    public static object Run(string python, string directory)
    {
        var comparer = OperatingSystem.IsWindows() ? StringComparer.OrdinalIgnoreCase : StringComparer.Ordinal;
        var parentKeys = Environment.GetEnvironmentVariables().Keys.Cast<string>().ToHashSet(comparer);
        if (!Path.IsPathFullyQualified(python) || !File.Exists(python) || parentKeys.Contains(Control) ||
            Keys.Any(parentKeys.Contains))
            throw new ProbeFailure("environment transport precondition failed");
        var observations = new List<JsonElement>();
        try
        {
            Environment.SetEnvironmentVariable(Control, "synthetic-inherited");
            foreach (string mode in new[] { "absent", "empty", "null", "text" })
            {
                CurrentCase = new { mode };
                var overlay = new Dictionary<string, string>();
                if (mode != "absent")
                    foreach (string key in Keys)
                        overlay[key] = mode == "null" ? null! : mode == "empty" ? "" : "synthetic-overlay";
                using var invoker = new ProcessInvoker(new QuietTrace());
                var stdout = new List<string>();
                bool stderr = false;
                invoker.OutputDataReceived += (_, e) => stdout.Add(e.Data);
                invoker.ErrorDataReceived += (_, _) => stderr = true;
                using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(30));
                int exit = invoker.ExecuteAsync(directory, python,
                    "-I -S environment_transport_child.py " + mode, overlay,
                    false, System.Text.Encoding.UTF8, true, timeout.Token).GetAwaiter().GetResult();
                if (exit is not (0 or 1) || stderr || stdout.Count != 1 || stdout[0].Length > 4096)
                    throw new ProbeFailure("environment transport child failed");
                using var json = JsonDocument.Parse(stdout[0]);
                var result = json.RootElement;
                if (result.EnumerateObject().Count() != 4 ||
                    result.GetProperty("case").GetString() != mode)
                    throw new ProbeFailure("environment transport shape failed");
                var presence = result.GetProperty("presence");
                if (presence.EnumerateObject().Count() != Keys.Length || Keys.Any(key =>
                    presence.GetProperty(key).GetString() is not ("absent" or "defined")))
                    throw new ProbeFailure("environment transport shape failed");
                // Only validated fixed fields enter diagnostics, never raw child output.
                bool valuesMatch = result.GetProperty("valuesMatch").GetBoolean();
                bool inheritedControlMatches = result.GetProperty("inheritedControlMatches").GetBoolean();
                CurrentCase = new { mode, presence = Keys.ToDictionary(key => key,
                    key => presence.GetProperty(key).GetString()), valuesMatch, inheritedControlMatches };
                if (Keys.Any(key => presence.GetProperty(key).GetString() != (mode == "absent" ? "absent" : "defined")))
                    throw new ProbeFailure("environment transport presence failed");
                if (!valuesMatch || !inheritedControlMatches)
                    throw new ProbeFailure("environment transport control failed");
                if (exit != 0) throw new ProbeFailure("environment transport inconsistent exit");
                observations.Add(result.Clone());
            }
        }
        finally { Environment.SetEnvironmentVariable(Control, null); }
        CurrentCase = null;
        return new { status = "passed", route = "package-sdk-invoker-to-isolated-python", cases = observations };
    }
}
