#nullable enable

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using GitHub.DistributedTask.WebApi;
using GitHub.Runner.Common;
using GitHub.Runner.Sdk;
using GitHub.Runner.Worker;
using GitHub.Runner.Worker.Container;
using GitHub.Runner.Worker.Container.ContainerHooks;
using GitHub.Runner.Worker.Handlers;
using Moq;
using Xunit;

namespace GitHub.Runner.Common.Tests.Worker;

public sealed class ShoutxDifferentialL0
{
#if !OS_WINDOWS
    [Fact]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public async Task ContainerPathArgumentUsesActualProcessInvokerTokenization()
    {
        if (!OperatingSystem.IsLinux())
        {
            return;
        }

        using var host = new TestHostContext(this);
        Directory.CreateDirectory(host.GetDirectory(WellKnownDirectory.Work));
        var root = Path.Combine(Path.GetTempPath(), $"shoutx-argv-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);
        try
        {
            var helper = Path.Combine(root, "record-argv");
            var output = Path.Combine(root, "argv");
            File.WriteAllText(helper, $"#!/bin/sh\n: > '{output}'\nfor arg do printf '%s\\n' \"$arg\" >> '{output}'; done\n");
            File.SetUnixFileMode(helper, UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
            var docker = new Mock<IDockerCommandManager>();
            docker.SetupGet(value => value.DockerPath).Returns(helper);
            host.SetSingleton<IDockerCommandManager>(docker.Object);
            host.SetSingleton<IContainerHookManager>(new Mock<IContainerHookManager>().Object);
            var global = new GlobalContext
            {
                Variables = new Variables(host, new Dictionary<string, VariableValue>()),
            };
            var context = new Mock<IExecutionContext>();
            context.SetupGet(value => value.Global).Returns(global);

            foreach (var item in new[]
            {
                (Path: "/normal", Expected: new[] { "exec", "-i", "--workdir", "/work", "-e", "PATH=/normal", "container", "command" }),
                (Path: "/bad\"quote", Expected: new[] { "exec", "-i", "--workdir", "/work", "-e", "PATH=/badquote container command " }),
                (Path: "/odd\\", Expected: new[] { "exec", "-i", "--workdir", "/work", "-e", "PATH=/odd\" container command " }),
                (Path: "/even\\\\", Expected: new[] { "exec", "-i", "--workdir", "/work", "-e", "PATH=/even\\", "container", "command" }),
            })
            {
                host.EnqueueInstance<IProcessInvoker>(new ProcessInvokerWrapper());
                var stepHost = new ContainerStepHost
                {
                    Container = new ContainerInfo { ContainerId = "container" },
                    PrependPath = item.Path,
                };
                stepHost.Initialize(host);
                var status = await stepHost.ExecuteAsync(
                    context.Object, "/work", "command", "", new Dictionary<string, string>(),
                    false, Encoding.UTF8, false, false, null!, CancellationToken.None);
                Assert.Equal(0, status);
                Assert.Equal(item.Expected, File.ReadAllLines(output));
            }
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }
#endif

    [Fact]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void PathOrderingFlowsThroughHandlerAndPathUtil()
    {
        using var host = new TestHostContext(this);
        host.EnqueueInstance<IActionCommandManager>(new Mock<IActionCommandManager>().Object);
        var prepend = new List<string> { "first", "second", "third" };
        var global = new GlobalContext { PrependPath = prepend };
        var context = new Mock<IExecutionContext>();
        context.SetupGet(value => value.Global).Returns(global);
        var variables = new Variables(host, new Dictionary<string, VariableValue>());
        var expectedPrepend = string.Join(Path.PathSeparator, prepend.AsEnumerable().Reverse());
        var environment = new Dictionary<string, string> { [Constants.PathVariable] = "original" };
        var handler = new ExposedHandler
        {
            ExecutionContext = context.Object,
            Environment = environment,
            RuntimeVariables = variables,
            StepHost = new Mock<IStepHost>().Object,
        };
        handler.Initialize(host);

        handler.ApplyPrependPath();

        var composed = expectedPrepend + Path.PathSeparator + "original";
        Assert.Equal(composed, environment[Constants.PathVariable]);

        handler.ApplyPrependPath();

        Assert.Equal(composed, environment[Constants.PathVariable]);
    }

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

    private sealed class ExposedHandler : Handler
    {
        public void ApplyPrependPath() => AddPrependPathToEnvironment();
    }
}
