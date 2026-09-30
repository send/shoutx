using System.Globalization;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using GitHub.Runner.Common;

// Only synthetic corpus data enters this probe. It never registers a worker.
static class Program
{
    sealed record IcuObservation(string binding, uint versionRaw, string? version);
    static string phase = "initialization";
    static object? testCase;

    static IcuObservation? ObserveIcuVersion(object? invariant, object? ascii)
    {
        // The inspected IcuInitSortHandle sets this flag; don't initialize ICU
        // artificially on NLS/invariant runs just to obtain a version number.
        if (invariant is not false || ascii is not true) return null;
        // Invoke CoreLib's own binding. Loading the standalone native shim can
        // query a separate, uninitialized instance on statically linked CoreCLR.
        var method = typeof(object).Assembly.GetType("Interop+Globalization")?.GetMethod(
            "GetICUVersion", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
        if (method is null) return null;
        uint version = unchecked((uint)(int)method.Invoke(null, null)!);
        string? text = version == 0 ? null : $"{version >> 24}.{(version >> 16) & 255}.{(version >> 8) & 255}.{version & 255}";
        return new("CoreLib:Interop.Globalization.GetICUVersion", version, text);
    }
    static readonly HashSet<string> Commands = new(StringComparer.OrdinalIgnoreCase)
        { "add-mask", "notice", "warning", "error" };
    static void Require(bool condition, string rule)
    {
        if (!condition) throw new InvalidOperationException(rule);
    }

    static object Identity(Assembly assembly, string directory)
    {
        string path = Path.GetFullPath(assembly.Location);
        var identity = new Dictionary<string, object?> {
            ["path"] = path,
            ["inPackage"] = string.Equals(Path.GetDirectoryName(path), directory,
                OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal),
            ["file"] = Path.GetFileName(path)
        };
        try
        {
            identity["sha256"] = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
            identity["informationalVersion"] = assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion;
            identity["moduleVersionId"] = assembly.ManifestModule.ModuleVersionId;
        }
        catch (Exception error) { identity["readErrorType"] = error.GetType().Name; }
        return identity;
    }

    static object? ModeFlag(string name)
    {
        var type = typeof(CultureInfo).Assembly.GetType("System.Globalization.GlobalizationMode");
        const BindingFlags flags = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
        // Unix builds can expose compile-time constant fields rather than properties.
        return type?.GetProperty(name, flags)?.GetValue(null) ?? type?.GetField(name, flags)?.GetValue(null);
    }

    static string DataEscape(string value) => value.Replace("%", "%25").Replace("\r", "%0D").Replace("\n", "%0A");
    static string Decode(JsonElement value) => Encoding.UTF8.GetString(Convert.FromBase64String(value.GetString()!));

    static int Corpus(string path, bool mask)
    {
        using var corpus = JsonDocument.Parse(File.ReadAllBytes(path));
        int count = 0;
        foreach (var item in corpus.RootElement.EnumerateArray())
        {
            testCase = new { corpus = mask ? "mask" : "annotation", index = count };
            string wire = Decode(item.GetProperty("command"));
            Require(wire.EndsWith('\n') && !wire[..^1].Contains('\n') && !wire.Contains('\r'), "wire framing mismatch");
            string line = wire[..^1];
            int separator = line.IndexOf("::", 2, StringComparison.Ordinal);
            Require(separator >= 0 && line.IndexOf("::", 2) == separator, "separator moved");
            Require(ActionCommand.TryParseV2(line, Commands, out var parsed), "V2 corpus parse failed");
            string expectedCommand = mask ? "add-mask" : item.GetProperty("severity").GetString()!;
            Require(parsed.Command == expectedCommand, "command mismatch");
            Require(parsed.Data == Decode(item.GetProperty(mask ? "value" : "message")), "data mismatch");
            if (mask) Require(parsed.Properties.Count == 0, "unexpected mask properties");
            else
            {
                // Parser-level evidence before file translation. Current fixtures'
                // POSIX post-extension properties equal their wire-level values;
                // a future transformed fixture needs a separate parser expectation.
                var expected = item.GetProperty("properties");
                Require(parsed.Properties.Count == expected.EnumerateObject().Count(), "property count mismatch");
                foreach (var property in expected.EnumerateObject())
                    Require(parsed.Properties.TryGetValue(property.Name, out var value) && value == Decode(property.Value), "property mismatch");
            }
            count++;
        }
        Require(count > 0, "empty corpus");
        return count;
    }

    static long ScalarChecks()
    {
        long count = 0;
        foreach (var header in new[] { "::add-mask::", "::warning title=ascii-'%3A%2C%25%0D%0A,file=src/a-b'c.rs::" })
        foreach (char first in new[] { 'A', ':', '%', ' ', '-', '\'', '#', '0' })
        for (int scalar = 1; scalar <= 0x10ffff; scalar++)
        {
            if (scalar is >= 0xd800 and <= 0xdfff) continue;
            testCase = new { header = header.StartsWith("::add-mask", StringComparison.Ordinal) ? "mask" : "annotation", first = (int)first, scalar };
            string data = first + char.ConvertFromUtf32(scalar) + " ##[error]literal::tail";
            string line = header + DataEscape(data);
            Require(line.IndexOf("::", 2) == header.Length - 2, "scalar separator moved");
            Require(ActionCommand.TryParseV2(line, Commands, out var parsed), "scalar V2 parse failed");
            bool mask = header.StartsWith("::add-mask", StringComparison.Ordinal);
            Require(parsed.Command == (mask ? "add-mask" : "warning") && parsed.Data == data, "scalar decode mismatch");
            Require(parsed.Properties.Count == (mask ? 0 : 2), "scalar properties mismatch");
            if (!mask) Require(parsed.Properties["title"] == "ascii-':,%\r\n" && parsed.Properties["file"] == "src/a-b'c.rs", "scalar property decode mismatch");
            count++;
        }
        return count;
    }

    static int Main(string[] args)
    {
        var report = new Dictionary<string, object?> { ["schemaVersion"] = 1, ["status"] = "failed" };
        try
        {
            Require(args.Length == 3, "expected evidence path and two corpus paths");
            string directory = Path.TrimEndingDirectorySeparator(Path.GetFullPath(AppContext.BaseDirectory));
            report["coreLibrary"] = Identity(typeof(object).Assembly, directory);
            report["parserAssembly"] = Identity(typeof(ActionCommand).Assembly, directory);
            report["workerAssembly"] = Identity(typeof(GitHub.Runner.Worker.ActionCommandManager).Assembly, directory);
            report["runtime"] = RuntimeInformation.FrameworkDescription;
            report["os"] = RuntimeInformation.OSDescription;
            report["architecture"] = RuntimeInformation.ProcessArchitecture.ToString();
            var invariant = ModeFlag("Invariant");
            var nls = ModeFlag("UseNls");
            var hybrid = ModeFlag("Hybrid");
            string backend = invariant is true ? "Invariant" : nls is true ? "NLS" : hybrid is true ? "Hybrid" :
                invariant is false && nls is false && hybrid is false ? "ICU" : "Unknown";
            report["globalization"] = new { invariant, nls, hybrid, backendFromFlags = backend };
            var cultures = new List<object>();
            report["cultures"] = cultures;
            foreach (string name in new[] { "", "en-US" })
            {
                phase = "culture-setup";
                testCase = new { culture = name };
                CultureInfo.CurrentCulture = CultureInfo.GetCultureInfo(name);
                var compare = CultureInfo.CurrentCulture.CompareInfo;
                object? ascii = typeof(CompareInfo).GetField("_isAsciiEqualityOrdinal", BindingFlags.Instance | BindingFlags.NonPublic)?.GetValue(compare);
                var icu = ObserveIcuVersion(invariant, ascii);
                var observation = new Dictionary<string, object?> {
                    ["culture"] = name, ["sortVersion"] = compare.Version.FullVersion, ["sortId"] = compare.Version.SortId,
                    ["asciiEqualityOrdinal"] = ascii, ["icu"] = icu,
                    ["backendObserved"] = invariant is true ? "Invariant" : nls is true ? "NLS" : hybrid is true ? "Hybrid" :
                        invariant is false && ascii is true && icu?.versionRaw is > 0 ? "ICU" : "Unknown",
                    ["icuSourcePreconditionsObserved"] = invariant is false && nls is not true && hybrid is not true && ascii is true && icu?.versionRaw is > 0
                };
                cultures.Add(observation);
                phase = "mask-corpus";
                observation["maskCases"] = Corpus(args[1], true);
                phase = "annotation-corpus";
                observation["annotationCases"] = Corpus(args[2], false);
                phase = "worker-effects";
                observation["workerEffects"] = WorkerProbe.Run(args[1], args[2], Path.Combine(Path.GetDirectoryName(args[0])!, "worker-trace.log"));
                phase = "scalar-checks";
                observation["scalarChecks"] = ScalarChecks();
            }
            report["status"] = "passed";
        }
        catch (Exception error)
        {
            report["errorType"] = error.GetType().Name;
            if (error.InnerException is not null) report["innerErrorType"] = error.InnerException.GetType().Name;
            if (error is InvalidOperationException) report["errorRule"] = error.Message;
            report["failedPhase"] = phase;
            report["testCase"] = testCase;
            if (phase == "worker-effects") report["workerCase"] = WorkerProbe.CurrentCase;
            Console.Error.WriteLine("package probe failed; see evidence (no corpus values logged)");
        }
        finally
        {
            try
            {
                string directory = Path.TrimEndingDirectorySeparator(Path.GetFullPath(AppContext.BaseDirectory));
                report["loadedManagedAssemblies"] = AppDomain.CurrentDomain.GetAssemblies()
                    .Where(a => !a.IsDynamic && a != typeof(Program).Assembly)
                    .Select(a => Identity(a, directory)).ToArray();
                report["dynamicAssemblyNames"] = AppDomain.CurrentDomain.GetAssemblies()
                    .Where(a => a.IsDynamic).Select(a => a.FullName).ToArray();
            }
            catch (Exception error)
            {
                report["status"] = "failed";
                report["identityErrorType"] = error.GetType().Name;
            }
            if (args.Length > 0) File.WriteAllText(args[0], JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
        }
        return Equals(report["status"], "passed") ? 0 : 1;
    }
}
