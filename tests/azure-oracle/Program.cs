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
                bool framing = line.EndsWith("\n", StringComparison.Ordinal)
                    && line.Count(c => c == '\n') == 1 && !line.Contains('\r');
                bool matched = false;
                if (framing && Command.TryParse(line.Substring(0, line.Length - 1),
                        item.GetProperty("decode").GetBoolean(), out var command))
                {
                    var expected = item.GetProperty("properties").EnumerateObject().ToArray();
                    matched = command.Area == "task"
                        && command.Event == item.GetProperty("event").GetString()
                        && command.Data == item.GetProperty("data").GetString()
                        && command.Properties.Count == expected.Length
                        && expected.All(p => command.Properties.Any(
                            q => q.Key == p.Name && q.Value == p.Value.GetString()));
                }
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
