using System.Security.Cryptography;
using System.Diagnostics;
using System.Text.Json;
using GitHub.Runner.Common;

// Experimental data-start policy only. No production encoder or acceptance
// rule uses this table. Keep headers ASCII to isolate the proposed change.
static class UnicodeCandidateProbe
{
    static readonly HashSet<string> Commands = new(StringComparer.OrdinalIgnoreCase) { "add-mask", "warning" };
    static readonly string[] Tails = { "x", "\u0301x", "\u0e33x", "\U0001f3fbx",
        "\ufe0f\u200d\u0301x", "\u200d\u0301##[warning]literal::tail" };
    static readonly int[] Starts = { 0x65e5, 0x1f600, 0x627, 0x939, 0xd55c, 0x1f1ef, 0xe40, 0xec0, 0x1100, 0x21 };

    static string Escape(string value) => value.Replace("%", "%25").Replace("\r", "%0D").Replace("\n", "%0A");
    static string? Check(string data, bool mask)
    {
        string header = mask ? "::add-mask::" : "::warning title=ascii-'%3A%2C%25%0D%0A,file=src/a-b'c.rs::";
        string line = header + Escape(data);
        if (line.IndexOf("::", 2) != header.Length - 2) return "separator";
        if (!ActionCommand.TryParseV2(line, Commands, out var parsed)) return "parse";
        if (parsed.Command != (mask ? "add-mask" : "warning")) return "command";
        if (parsed.Data != data) return "data";
        if (parsed.Properties.Count != (mask ? 0 : 2) || (!mask &&
            (parsed.Properties.GetValueOrDefault("title") != "ascii-':,%\r\n" ||
             parsed.Properties.GetValueOrDefault("file") != "src/a-b'c.rs"))) return "properties";
        return null;
    }

    public static Dictionary<string, object?> Run()
    {
        var timer = Stopwatch.StartNew();
        using var stream = typeof(UnicodeCandidateProbe).Assembly.GetManifestResourceStream("unicode-candidate.json")
            ?? throw new ProbeFailure("missing Unicode candidate resource");
        using var bytes = new MemoryStream();
        stream.CopyTo(bytes);
        byte[] raw = bytes.ToArray();
        using var document = JsonDocument.Parse(raw);
        var table = document.RootElement;
        if (table.GetProperty("schemaVersion").GetInt32() != 1 || !table.GetProperty("researchOnly").GetBoolean() ||
            table.GetProperty("unicodeVersion").GetString() != "14.0.0")
            throw new ProbeFailure("unexpected Unicode candidate identity");
        var points = new List<int>();
        int previous = 0;
        foreach (var range in table.GetProperty("ranges").EnumerateArray())
        {
            if (range.GetArrayLength() != 2) throw new ProbeFailure("invalid candidate interval");
            int start = range[0].GetInt32(), end = range[1].GetInt32();
            if (start <= previous || end < start || end > 0x10ffff || (start <= 0xdfff && end >= 0xd800))
                throw new ProbeFailure("invalid candidate interval");
            for (int cp = start; cp <= end; cp++) points.Add(cp);
            previous = end;
        }
        if (points.Count != 142081 || table.GetProperty("count").GetInt32() != points.Count ||
            Starts.Any(cp => !points.Contains(cp))) throw new ProbeFailure("unexpected candidate coverage");
        long candidateChecks = 0, pairChecks = 0, failures = 0;
        var examples = new List<object>();
        int candidateExamples = 0, pairExamples = 0;
        void Record(string? reason, string suite, int first, int index, bool mask)
        {
            if (reason is null) return;
            failures++;
            // Never include raw Unicode, command-shaped input, or exception text.
            bool retain = suite == "candidate" ? candidateExamples++ < 8 : pairExamples++ < 8;
            if (retain) examples.Add(new { suite, reason, firstScalar = first,
                tailIndex = suite == "candidate" ? (int?)index : null,
                secondScalar = suite == "pair" ? (int?)index : null, mask });
        }
        foreach (int cp in points)
        for (int tail = 0; tail < Tails.Length; tail++)
        foreach (bool mask in new[] { false, true })
        {
            candidateChecks++;
            Record(Check(char.ConvertFromUtf32(cp) + Tails[tail], mask), "candidate", cp, tail, mask);
        }
        foreach (int first in Starts)
        for (int second = 1; second <= 0x10ffff; second++)
        {
            if (second is >= 0xd800 and <= 0xdfff) continue;
            pairChecks++;
            Record(Check(char.ConvertFromUtf32(first) + char.ConvertFromUtf32(second) + "x", false), "pair", first, second, false);
        }
        return new() {
            ["unicodeVersion"] = "14.0.0", ["researchOnly"] = true,
            ["tableSha256"] = Convert.ToHexString(SHA256.HashData(raw)).ToLowerInvariant(),
            ["candidateCount"] = points.Count, ["candidateChecks"] = candidateChecks,
            ["pairChecks"] = pairChecks, ["failures"] = failures, ["examples"] = examples,
            ["elapsedMilliseconds"] = timer.ElapsedMilliseconds
        };
    }
}
