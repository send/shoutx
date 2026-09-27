#nullable enable

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using GitHub.Runner.Worker;
using Xunit;

namespace GitHub.Runner.Common.Tests.Worker;

public sealed class ShoutxDifferentialL0
{
    [Fact]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void EnvironmentFileParserMatchesSharedCorpus()
    {
        var corpusPath = Environment.GetEnvironmentVariable("SHOUTX_CORPUS");
        Assert.False(string.IsNullOrEmpty(corpusPath));
        var corpus = JsonSerializer.Deserialize<List<CorpusCase>>(
            File.ReadAllText(corpusPath!),
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
        Assert.NotNull(corpus);

        var root = Path.Combine(Path.GetTempPath(), $"shoutx-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);
        try
        {
            foreach (var item in corpus!)
            {
                var path = Path.Combine(root, item.Id);
                File.WriteAllBytes(path, Convert.FromBase64String(item.Input));
                var success = true;
                List<CorpusRecord> actual = [];
                try
                {
                    actual = new EnvFileKeyValuePairs(null!, path)
                        .Select(pair => new CorpusRecord(Encode(pair.Key), Encode(pair.Value)))
                        .ToList();
                }
                catch
                {
                    success = false;
                }

                Assert.Equal(item.Success, success);
                if (success)
                {
                    var expected = OperatingSystem.IsWindows() && item.WindowsRecords is not null
                        ? item.WindowsRecords
                        : item.Records;
                    Assert.Equal(expected, actual);
                }
            }
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    private static string Encode(string value) =>
        Convert.ToBase64String(Encoding.UTF8.GetBytes(value));

    private sealed record CorpusCase(
        string Id,
        string Input,
        bool Success,
        IReadOnlyList<CorpusRecord> Records,
        IReadOnlyList<CorpusRecord>? WindowsRecords);

    private sealed record CorpusRecord(string Name, string Value);
}
