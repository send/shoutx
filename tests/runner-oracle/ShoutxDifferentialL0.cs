#nullable enable

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using GitHub.Runner.Common;
using GitHub.Runner.Worker;
using Moq;
using Xunit;

namespace GitHub.Runner.Common.Tests.Worker;

public sealed class ShoutxDifferentialL0
{
    [Fact]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void PathDuplicateComparisonNativeObservation()
    {
        var path = Path.GetTempFileName();
        try
        {
            File.WriteAllText(path, "/a\n/a\u200b\n", new UTF8Encoding(false));
            var global = new GlobalContext { PrependPath = [] };
            var context = new Mock<IExecutionContext>();
            context.SetupGet(value => value.Global).Returns(global);
            context.SetupGet(value => value.DeferredPrependPath).Returns((List<string>)null!);

            new AddPathFileCommand().ProcessCommand(context.Object, path, null!);

            Assert.Equal(["/a\u200b"], global.PrependPath);
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void PathFileParserMatchesSharedCorpus()
    {
        var corpusPath = Environment.GetEnvironmentVariable("SHOUTX_PATH_CORPUS");
        Assert.False(string.IsNullOrEmpty(corpusPath));
        var corpus = JsonSerializer.Deserialize<List<PathCase>>(
            File.ReadAllText(corpusPath!),
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
        Assert.NotNull(corpus);

        var root = Path.Combine(Path.GetTempPath(), $"shoutx-path-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);
        try
        {
            foreach (var item in corpus!)
            {
                var path = Path.Combine(root, item.Id);
                File.WriteAllBytes(path, Convert.FromBase64String(item.Input));
                var global = new GlobalContext { PrependPath = [] };
                var context = new Mock<IExecutionContext>();
                context.SetupGet(value => value.Global).Returns(global);
                context.SetupGet(value => value.DeferredPrependPath).Returns((List<string>)null!);

                new AddPathFileCommand().ProcessCommand(context.Object, path, null!);

                var actual = global.PrependPath.Select(Encode).ToList();
                Assert.True(item.Paths.SequenceEqual(actual), $"case {item.Id}: path mismatch");
                var effective = global.PrependPath.AsEnumerable().Reverse().Select(Encode).ToList();
                Assert.True(item.Effective.SequenceEqual(effective), $"case {item.Id}: ordering mismatch");
            }
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

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

                Assert.True(item.Success == success, $"case {item.Id}: success mismatch");
                if (success)
                {
                    var expected = OperatingSystem.IsWindows() && item.WindowsRecords is not null
                        ? item.WindowsRecords
                        : item.Records;
                    Assert.True(
                        expected.SequenceEqual(actual),
                        $"case {item.Id}: record mismatch");
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
        [property: JsonPropertyName("windows_records")]
        IReadOnlyList<CorpusRecord>? WindowsRecords);

    private sealed record CorpusRecord(string Name, string Value);
    private sealed record PathCase(
        string Id,
        string Input,
        IReadOnlyList<string> Paths,
        IReadOnlyList<string> Effective);
}
