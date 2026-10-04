using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;

int checks = 0;
void Check(bool condition)
{
    if (!condition) throw new InvalidOperationException("Fixture assertion failed.");
    checks++;
}
var temporary = Directory.CreateTempSubdirectory("shoutx-member-fixture-");
try
{
    string bin = temporary.FullName;
    string fixture = Path.Combine(bin, "Fixture.dll");
    string deps = Path.Combine(bin, "Runner.Worker.deps.json");
    byte[] assembly = File.ReadAllBytes(typeof(Fixture).Assembly.Location);
    File.WriteAllBytes(fixture, assembly);
    void WriteDeps(string[] assets, bool alternatives = false)
    {
        var runtime = assets.ToDictionary(x => x, _ => new { }, StringComparer.Ordinal);
        var library = new Dictionary<string, object> { ["runtime"] = runtime };
        if (alternatives) library["runtimeTargets"] = new { unreviewed = new { } };
        File.WriteAllText(deps, JsonSerializer.Serialize(new {
            runtimeTarget = new { name = "fixture" },
            targets = new Dictionary<string, object> { ["fixture"] = new Dictionary<string, object> { ["fixture/1"] = library } }
        }));
    }
    void Reject(Action action, Type? expectedType = null)
    {
        bool rejected = false;
        try { action(); }
        catch (Exception e) when (e is IOException or InvalidOperationException or KeyNotFoundException or JsonException or BadImageFormatException)
        { rejected = true; if (expectedType is not null) Check(e.GetType() == expectedType); }
        Check(rejected);
    }
    WriteDeps(["lib/net8.0/Fixture.dll"]);
    var result = ReferenceInventory.Scan(bin);
    Check(result.status == "scanned-member-references" && result.assemblies.Length == 1);
    Check(result.assemblies[0].sha256 == Convert.ToHexString(SHA256.HashData(assembly)).ToLowerInvariant());
    Check(result.depsSha256 == Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(deps))).ToLowerInvariant());
    Check(result.assemblies[0].selectedReferences.Any(r => r.owner == "System.Globalization.CultureInfo" && r.member == "set_CurrentCulture"));
    Check(result.assemblies[0].selectedReferences.Any(r => r.owner == "System.AppContext" && r.member == "SetSwitch"));
    Check(result.assemblies[0].selectedReferences.Any(r => r.owner == "System.AppDomain" && r.member == "SetData"));
    Check(result.assemblies[0].selectedReferences.Any(r => r.parentKind == "TypeSpecification" && r.owner == "unresolved"));
    string[] expectedNames = ["ClearCachedData", "SetCurrentCulture", "SetDefaultCulture", "SetData",
        "SetEnvironmentVariable", "SetSwitch", "SuppressFlow", "set_CurrentCulture", "set_CurrentUICulture",
        "set_DefaultThreadCurrentCulture", "set_DefaultThreadCurrentUICulture"];
    Check(result.selectedMemberNames.SequenceEqual(expectedNames));
    Check(result.assemblies[0].selectedReferences.Select(r => r.member).Distinct().Order(StringComparer.Ordinal)
        .SequenceEqual(expectedNames.Order(StringComparer.Ordinal)));
    Check(result.assemblies[0].memberReferenceCount > result.assemblies[0].selectedReferences.Length);
    Check(!JsonSerializer.Serialize(result).Contains(JsonSerializer.Serialize(bin)[1..^1], StringComparison.Ordinal));
    Check(!result.assemblies[0].selectedReferences.Any(r => r.member == "get_CurrentCulture"));
    foreach (string[] assets in new[] {
        Array.Empty<string>(), new[] { "../Fixture.dll" }, new[] { "/Fixture.dll" },
        new[] { "C:/Fixture.dll" }, new[] { "lib\\Fixture.dll" }, new[] { "x//Fixture.dll" },
        new[] { "Fixture.exe" }, new[] { "a/Fixture.dll", "b/Fixture.dll" },
        new[] { "Fixture.dll", "fixture.dll" },
        new[] { "secret\nFixture.dll" }
    }) { WriteDeps(assets); Reject(() => ReferenceInventory.Scan(bin), typeof(InvalidOperationException)); }
    WriteDeps(["missing.dll"]);
    Reject(() => ReferenceInventory.Scan(bin), typeof(FileNotFoundException));
    WriteDeps(["Fixture.dll"], alternatives: true);
    Reject(() => ReferenceInventory.Scan(bin));
    WriteDeps(Enumerable.Range(0, 513).Select(i => $"Fixture{i}.dll").ToArray());
    Reject(() => ReferenceInventory.Scan(bin), typeof(InvalidOperationException));
    WriteDeps(["Fixture.dll"]);
    File.WriteAllText(fixture, "not a PE assembly");
    Reject(() => ReferenceInventory.Scan(bin));
    File.WriteAllBytes(fixture, assembly);
    using (var stream = File.OpenWrite(fixture)) stream.SetLength(128L * 1024 * 1024 + 1);
    Reject(() => ReferenceInventory.Scan(bin));
    File.WriteAllBytes(fixture, assembly);
    File.WriteAllText(deps, "{}");
    Reject(() => ReferenceInventory.Scan(bin));
    WriteDeps(["Fixture.dll"]);
    File.WriteAllText(deps, File.ReadAllText(deps)[..^1] + ",\"runtimeTarget\":{\"name\":\"fixture\"}}");
    Reject(() => ReferenceInventory.Scan(bin));
    File.WriteAllText(deps, "not json");
    Reject(() => ReferenceInventory.Scan(bin));
    WriteDeps(["Fixture.dll"]);
    File.AppendAllText(deps, new string(' ', 4 * 1024 * 1024));
    Reject(() => ReferenceInventory.Scan(bin));
    File.Delete(deps);
    Reject(() => ReferenceInventory.Scan(bin));
    Console.WriteLine($"Managed reference fixture checks passed: {checks}");
}
finally { temporary.Delete(recursive: true); }

static class Fixture
{
    // Kept in metadata but never called or loaded by the scanner.
    public static void NeverExecute()
    {
        _ = CultureInfo.CurrentCulture;
        CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
        CultureInfo.CurrentUICulture = CultureInfo.InvariantCulture;
        CultureInfo.DefaultThreadCurrentCulture = CultureInfo.InvariantCulture;
        CultureInfo.DefaultThreadCurrentUICulture = CultureInfo.InvariantCulture;
        CultureInfo.InvariantCulture.ClearCachedData();
        Environment.SetEnvironmentVariable("shoutx.synthetic", null);
        using var flow = System.Threading.ExecutionContext.SuppressFlow();
        AppContext.SetSwitch("shoutx.synthetic", true);
        AppDomain.CurrentDomain.SetData("shoutx.synthetic", true);
        GenericFixture<int>.SetSwitch();
        GenericFixture<int>.SetCurrentCulture();
        GenericFixture<int>.SetDefaultCulture();
        throw new InvalidOperationException("Fixture method must never execute.");
    }
}

static class GenericFixture<T>
{
    public static void SetSwitch() { }
    public static void SetCurrentCulture() { }
    public static void SetDefaultCulture() { }
}
