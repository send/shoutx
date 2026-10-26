using System;
using System.Linq;
using System.Text;
using System.Text.Json;
using Microsoft.VisualStudio.Services.Agent;

// Only the unrelated constructor assertion dependency is stubbed. Parsing and
// escaping are compiled unchanged from the hash-verified upstream sources.
namespace Microsoft.VisualStudio.Services.Agent.Util
{
    public static class ArgUtil
    {
        public static void NotNullOrEmpty(string value, string name)
        {
            if (string.IsNullOrEmpty(value)) throw new ArgumentException(name);
        }
    }
}

class Program
{
    static bool Matches(string line, JsonElement expected, bool decode)
    {
        if (!Command.TryParse(line, decode, out var command)) return false;
        var properties = expected.GetProperty("properties").EnumerateObject().ToArray();
        var area = expected.TryGetProperty("area", out var requestedArea)
            ? requestedArea.GetString() : "task";
        return command.Area == area
            && command.Event == expected.GetProperty("event").GetString()
            && command.Data == expected.GetProperty("data").GetString()
            && command.Properties.Count == properties.Length
            && properties.All(p => command.Properties.Any(
                q => q.Key == p.Name && q.Value == p.Value.GetString()));
    }

    static int Main()
    {
        int count = 0;
        int negative = 0;
        try
        {
            string row;
            while ((row = Console.ReadLine()) != null)
            {
                using var document = JsonDocument.Parse(row);
                var item = document.RootElement;
                var bytes = Convert.FromBase64String(item.GetProperty("record").GetString());
                var line = new UTF8Encoding(false, true).GetString(bytes);
                var expected = item.TryGetProperty("records", out var records)
                    ? records.EnumerateArray().ToArray() : new[] { item };
                var lines = line.Split('\n');
                bool matched = expected.Length > 0
                    && line.EndsWith("\n", StringComparison.Ordinal)
                    && !line.Contains('\r') && lines.Length == expected.Length + 1
                    && expected.Select((entry, index) => Matches(lines[index], entry,
                        item.GetProperty("decode").GetBoolean())).All(value => value);
                var wanted = item.GetProperty("match").GetBoolean();
                if (matched != wanted) throw new Exception("case mismatch");
                if (!wanted) negative++;
                count++;
            }
            if (count < 300 || negative < 4) throw new Exception("missing coverage");
            Console.WriteLine(JsonSerializer.Serialize(new { cases = count, negativeControls = negative }));
            return 0;
        }
        catch
        {
            Console.Error.WriteLine("Azure source-parser verification failed (case " + count + ")");
            return 1;
        }
    }
}
