using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;

public static class ReferenceInventory
{
    const int DepsCap = 4 * 1024 * 1024;
    const long AssemblyCap = 128L * 1024 * 1024;
    static readonly string[] Members = [
        "ClearCachedData", "SetCurrentCulture", "SetDefaultCulture", "SetData", "SetEnvironmentVariable",
        "SetSwitch", "SuppressFlow", "set_CurrentCulture", "set_CurrentUICulture",
        "set_DefaultThreadCurrentCulture", "set_DefaultThreadCurrentUICulture"
    ];

    public sealed record SelectedReference(string member, string owner, string parentKind);
    public sealed record AssemblyObservation(string name, string sha256, int memberReferenceCount,
        SelectedReference[] selectedReferences);
    public sealed record Host(string runtime, string architecture, string os);
    public sealed record Report(int schemaVersion, string status, string scope, string depsSha256,
        string runtimeTarget, Host scannerHost, string[] selectedMemberNames, AssemblyObservation[] assemblies);

    static void Require(bool condition)
    {
        if (!condition) throw new InvalidOperationException("Unsupported package metadata.");
    }

    static string Digest(Stream stream, long expectedLength)
    {
        using var digest = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        byte[] buffer = new byte[1024 * 1024];
        long count = 0;
        int read;
        while ((read = stream.Read(buffer)) != 0)
        {
            count += read;
            Require(count <= expectedLength);
            digest.AppendData(buffer, 0, read);
        }
        Require(count == expectedLength);
        return Convert.ToHexString(digest.GetHashAndReset()).ToLowerInvariant();
    }

    static void CheckJsonKeys(JsonElement value)
    {
        if (value.ValueKind == JsonValueKind.Object)
        {
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (var property in value.EnumerateObject())
            {
                Require(names.Add(property.Name));
                CheckJsonKeys(property.Value);
            }
        }
        else if (value.ValueKind == JsonValueKind.Array)
            foreach (var item in value.EnumerateArray()) CheckJsonKeys(item);
    }

    public static Report Scan(string directory)
    {
        string bin = Path.GetFullPath(directory);
        string depsPath = Path.Combine(bin, "Runner.Worker.deps.json");
        byte[] bytes;
        using (var input = File.OpenRead(depsPath))
        {
            Require(input.Length is > 0 and <= DepsCap);
            bytes = new byte[checked((int)input.Length)];
            input.ReadExactly(bytes);
            Require(input.ReadByte() == -1);
        }
        using var document = JsonDocument.Parse(bytes, new JsonDocumentOptions { MaxDepth = 64 });
        var root = document.RootElement;
        CheckJsonKeys(root);
        string target = root.GetProperty("runtimeTarget").GetProperty("name").GetString()
            ?? throw new InvalidOperationException();
        Require(target.Length is > 0 and <= 256);
        var selected = root.GetProperty("targets").GetProperty(target);
        var paths = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var library in selected.EnumerateObject())
        {
            // This tool deliberately supports the reviewed flat runtime assets,
            // not runtimeTargets/RID fallback or resources resolution.
            if (library.Value.TryGetProperty("runtimeTargets", out var alternatives))
                Require(alternatives.ValueKind == JsonValueKind.Object && !alternatives.EnumerateObject().Any());
            if (!library.Value.TryGetProperty("runtime", out var runtime)) continue;
            foreach (var asset in runtime.EnumerateObject())
            {
                var parts = asset.Name.Split('/');
                Require(parts.Length > 0 && parts.All(p => p.Length is > 0 and <= 256 && p is not "." and not ".." &&
                    !p.Any(c => c is '\\' or ':' || char.IsControl(c))));
                string leaf = parts[^1];
                Require(leaf.EndsWith(".dll", StringComparison.OrdinalIgnoreCase) && paths.TryAdd(leaf, asset.Name));
                Require(paths.Count <= 512);
            }
        }
        Require(paths.Count > 0);
        var observations = new List<AssemblyObservation>();
        long totalBytes = 0;
        foreach (string name in paths.Keys.Order(StringComparer.Ordinal))
        {
            using var stream = File.OpenRead(Path.Combine(bin, name));
            long length = stream.Length;
            Require(length is > 0 and <= AssemblyCap);
            totalBytes += length;
            Require(totalBytes <= 1024L * 1024 * 1024);
            string digest = Digest(stream, length);
            Require(stream.Position == length && stream.Length == length);
            stream.Position = 0;
            using var pe = new PEReader(stream, PEStreamOptions.LeaveOpen);
            Require(pe.HasMetadata);
            var metadata = pe.GetMetadataReader();
            Require(metadata.MemberReferences.Count <= 1_000_000);
            var references = new List<SelectedReference>();
            foreach (var handle in metadata.MemberReferences)
            {
                var member = metadata.GetMemberReference(handle);
                string method = metadata.GetString(member.Name);
                if (!Members.Contains(method, StringComparer.Ordinal)) continue;
                string owner;
                if (member.Parent.Kind == HandleKind.TypeReference)
                {
                    var type = metadata.GetTypeReference((TypeReferenceHandle)member.Parent);
                    owner = type.ResolutionScope.Kind == HandleKind.TypeReference ? "unresolved-nested-type" :
                        metadata.GetString(type.Namespace) + "." + metadata.GetString(type.Name);
                }
                else if (member.Parent.Kind == HandleKind.TypeDefinition)
                {
                    var type = metadata.GetTypeDefinition((TypeDefinitionHandle)member.Parent);
                    owner = metadata.GetString(type.Namespace) + "." + metadata.GetString(type.Name);
                }
                else owner = "unresolved";
                Require(owner.Length <= 1024 && references.Count < 4096);
                references.Add(new(method, owner, member.Parent.Kind.ToString()));
            }
            Require(stream.Length == length);
            observations.Add(new(name, digest, metadata.MemberReferences.Count,
                references.Distinct().OrderBy(r => r.owner, StringComparer.Ordinal)
                    .ThenBy(r => r.member, StringComparer.Ordinal).ThenBy(r => r.parentKind, StringComparer.Ordinal).ToArray()));
        }
        return new(1, "scanned-member-references",
            "Selected names in MemberRef tables of active deps runtime assets; not callsites, MethodDef calls, reflection or live loaded state.",
            Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(), target,
            new(RuntimeInformation.FrameworkDescription, RuntimeInformation.ProcessArchitecture.ToString(), RuntimeInformation.OSDescription),
            Members.ToArray(), observations.ToArray());
    }
}
