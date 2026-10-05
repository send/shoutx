using System.Globalization;
using System.Text.Json;
using System.Security.Cryptography;
using GitHub.Runner.Common;

// Local, synthetic integration check. No raw values or command records in logs.
// This is not an acceptance table, a full-domain proof, or a worker-effects test.
string Escape(string value) => value.Replace("%", "%25").Replace("\r", "%0D")
    .Replace("\n", "%0A").Replace(":", "%3A").Replace(",", "%2C");
var values = new[] { "日本語", "😀", "العربية", "हिन्दी", "ภาษาไทย", "Ελληνικά",
    "עברית", "e\u0301", "\u0301", "\u200b", "\u0640", "\uff1a", "\ufe55",
    "x::y,title=z", "x%3A", "x\r\ny", "\u0301::x", "x\u0301" };
var commands = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "warning", "add-mask" };
var results = new List<object>();
bool anyFailure = false;
foreach (var culture in new[] { "", "en-US" })
{
    CultureInfo.CurrentCulture = CultureInfo.GetCultureInfo(culture);
    int cases = 0;
    var failures = new List<object>();
    for (int i = 0; i < values.Length; i++)
    foreach (string property in new[] { "title", "file" })
    foreach (string tail in new[] { "", ",line=1" })
    {
        string header = "::warning " + property + "=" + Escape(values[i]) + tail;
        string wire = header + (values[i].Any(c => c > 127) ? "," : "") + "::A literal::tail";
        int expectedCount = tail.Length == 0 ? 1 : 2;
        bool ok = ActionCommand.TryParseV2(wire, commands, out var parsed);
        bool equal = ok && parsed.Command == "warning" && parsed.Data == "A literal::tail"
            && parsed.Properties.Count == expectedCount
            && parsed.Properties.GetValueOrDefault(property) == values[i]
            && (tail.Length == 0 || parsed.Properties.GetValueOrDefault("line") == "1");
        if (!equal) failures.Add(new { mismatch = true });
        cases++;
    }
    long startCases = 0, startFailures = 0;
    
    if (args.Length != 0)
    {
        using var candidate = JsonDocument.Parse(File.ReadAllBytes(args[0]));
        foreach (var range in candidate.RootElement.GetProperty("ranges").EnumerateArray())
        for (int cp = range[0].GetInt32(); cp <= range[1].GetInt32(); cp++)
        foreach (string tail in new[] { "x", "\u0301::file=other::tail ##[warning]literal" })
        foreach (string command in new[] { "warning", "add-mask" })
        {
            string value = char.ConvertFromUtf32(cp) + tail;
            string prefix = "::" + command + "::";
            string wire = prefix + value.Replace("%", "%25").Replace("\r", "%0D").Replace("\n", "%0A");
            bool ok = ActionCommand.TryParseV2(wire, commands, out var parsed);
            if (!ok || parsed.Command != command || parsed.Data != value || parsed.Properties.Count != 0)
            {
                startFailures++;
            }
            startCases++;
        }
    }
    long headerCases = 0, headerFailures = 0;
    for (int cp = 1; cp <= 0x10ffff; cp++)
    {
        if (cp is >= 0xd800 and <= 0xdfff) continue;
        string scalar = char.ConvertFromUtf32(cp);
        // Final properties matter: a following numeric field is not equivalent.
        // Whitespace tails are outside the CLI contract, so keep those interior.
        string value = "X" + scalar + scalar + (char.IsWhiteSpace(scalar, 0) ? "X" : "");
        foreach (var field in new[] { "title", "file", "both" })
        {
            string properties = field == "both"
                ? "title=" + Escape(value) + ",file=" + Escape(value) + ",line=1"
                : field + "=" + Escape(value);
            string wire = "::warning " + properties + (cp > 127 ? "," : "") + "::,file=x,line=9::tail";
            bool ok = ActionCommand.TryParseV2(wire, commands, out var parsed);
            bool equal = ok && parsed.Command == "warning" && parsed.Data == ",file=x,line=9::tail"
                && parsed.Properties.Count == (field == "both" ? 3 : 1);
            if (equal && field == "both")
                equal = parsed.Properties.GetValueOrDefault("title") == value
                    && parsed.Properties.GetValueOrDefault("file") == value
                    && parsed.Properties.GetValueOrDefault("line") == "1";
            else if (equal)
                equal = parsed.Properties.GetValueOrDefault(field) == value;
            if (!equal) headerFailures++;
            headerCases++;
        }
    }
    anyFailure |= failures.Count != 0 || startFailures != 0 || headerFailures != 0;
    results.Add(new { culture, sortVersion = CultureInfo.CurrentCulture.CompareInfo.Version.FullVersion,
        cases, failures, startCases, startFailures, headerCases, headerFailures });
}
var icuGetter = typeof(object).Assembly.GetType("Interop+Globalization")?.GetMethod(
    "GetICUVersion", System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.Public
    | System.Reflection.BindingFlags.NonPublic);
uint icu = icuGetter == null ? 0 : unchecked((uint)(int)icuGetter.Invoke(null, null));
string report = JsonSerializer.Serialize(new {
    coreLibrarySha256 = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(typeof(object).Assembly.Location))).ToLowerInvariant(),
    candidateSha256 = args.Length == 0 ? null : Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(args[0]))).ToLowerInvariant(),
    runtime = Environment.Version.ToString(), os = Environment.OSVersion.ToString(),
    icu = $"{icu >> 24}.{(icu >> 16) & 255}.{(icu >> 8) & 255}.{icu & 255}",
    runnerCommonSha256 = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(typeof(ActionCommand).Assembly.Location))).ToLowerInvariant(),
    results }, new JsonSerializerOptions { WriteIndented = true });
Console.WriteLine(report);
if (args.Length > 1) File.WriteAllText(args[1], report + "\n");
return anyFailure ? 1 : 0;
