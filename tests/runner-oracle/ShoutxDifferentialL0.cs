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
using GitHub.DistributedTask.Pipelines.ContextData;
using GitHub.DistributedTask.Logging;
using GitHub.DistributedTask.WebApi;
using GitHub.Runner.Common;
using GitHub.Runner.Sdk;
using GitHub.Runner.Worker;
using GitHub.Runner.Worker.Container;
using GitHub.Runner.Worker.Container.ContainerHooks;
using GitHub.Runner.Worker.Handlers;
using Moq;
using Sdk.RSWebApi.Contracts;
using Xunit;
using Pipelines = GitHub.DistributedTask.Pipelines;

namespace GitHub.Runner.Common.Tests.Worker;

public sealed class ShoutxDifferentialL0
{
    [Fact]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void AnnotationCommandsMatchRunnerParserAndExtensions()
    {
        var corpusPath = Environment.GetEnvironmentVariable("SHOUTX_ANNOTATION_CORPUS");
        Assert.False(string.IsNullOrEmpty(corpusPath));
        var corpus = JsonSerializer.Deserialize<List<AnnotationCase>>(
            File.ReadAllText(corpusPath!),
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
        Assert.NotNull(corpus);

        foreach (var item in corpus!)
        {
            var (host, manager, context) = CreateActionCommandContext();
            using (host)
            {
                var actual = new List<Issue>();
                context.Setup(value => value.AddIssue(
                        It.IsAny<Issue>(), It.IsAny<ExecutionContextLogOptions>()))
                    .Callback<Issue, ExecutionContextLogOptions>((issue, _) => actual.Add(issue));

                var bytes = Convert.FromBase64String(item.Command);
                Assert.Equal((byte)'\n', bytes[^1]);
                var line = Encoding.UTF8.GetString(bytes, 0, bytes.Length - 1);

                Assert.True(manager.TryProcessCommand(context.Object, line, null!));
                var issue = Assert.Single(actual);
                Assert.Equal(item.Severity, issue.Type.ToString(), ignoreCase: true);
                Assert.Equal(Decode(item.Message), issue.Message);
                var expectedProperties = OperatingSystem.IsWindows()
                    ? item.WindowsProperties
                    : item.Properties;
                Assert.Equal(expectedProperties.ContainsKey("file") ? "Code" : "General", issue.Category);
                Assert.Equal(
                    expectedProperties.ToDictionary(pair => pair.Key, pair => Decode(pair.Value)),
                    issue.Data.Where(pair => expectedProperties.ContainsKey(pair.Key))
                        .ToDictionary(pair => pair.Key, pair => pair.Value));
                Assert.Equal(expectedProperties.Count, issue.Data.Count);
            }
        }
    }

    [Theory]
    [InlineData("\u0301")]
    [InlineData("\uFF9E")]
    [InlineData("\uFF9F")]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void LeadingCollationMarksCanMoveTheAnnotationSeparator(string prefix)
    {
        var (host, manager, context) = CreateActionCommandContext();
        using (host)
        {
            Issue? actual = null;
            context.Setup(value => value.AddIssue(
                    It.IsAny<Issue>(), It.IsAny<ExecutionContextLogOptions>()))
                .Callback<Issue, ExecutionContextLogOptions>((issue, _) => actual = issue);

            var line = $"::warning title=safe::{prefix},file=/etc/passwd,line=3::tail";
            Assert.True(manager.TryProcessCommand(context.Object, line, null!));
            Assert.NotNull(actual);
            Assert.Equal("tail", actual!.Message);
            Assert.Equal("etc/passwd", actual.Data["file"]);
            Assert.Equal("3", actual.Data["line"]);
        }
    }

    [Theory]
    [InlineData("\u0301")]
    [InlineData("\uFF9E")]
    [InlineData("\uFF9F")]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void LeadingCollationMarksCanReachTheLegacyCommandParser(string prefix)
    {
        var (host, manager, context) = CreateActionCommandContext();
        using (host)
        {
            const string injected = "legacy-injected-mask";
            var line = $"::add-mask::{prefix}##[add-mask]{injected}";

            Assert.True(manager.TryProcessCommand(context.Object, line, null!));
            Assert.Equal("***", host.SecretMasker.MaskSecrets(injected));
        }
    }

    [Theory]
    [InlineData("\u0301")]
    [InlineData("\uFF9E")]
    [InlineData("\uFF9F")]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void LeadingCollationMarksCanBypassMaskRegistration(string prefix)
    {
        var (host, manager, context) = CreateActionCommandContext();
        using (host)
        {
            var value = $"{prefix}unregistered-secret";
            var line = $"::add-mask::{value}";

            Assert.False(manager.TryProcessCommand(context.Object, line, null!));
            Assert.Equal(value, host.SecretMasker.MaskSecrets(value));
        }
    }

    [Theory]
    [InlineData("\u0600")]
    [InlineData("\u0605")]
    [InlineData("\u06DD")]
    [InlineData("\u070F")]
    [InlineData("\u0890")]
    [InlineData("\u0891")]
    [InlineData("\u08E2")]
    [InlineData("\u0D4E")]
    [InlineData("\U000110BD")]
    [InlineData("\U000110CD")]
    [InlineData("\U000111C2")]
    [InlineData("\U000111C3")]
    [InlineData("\U0001193F")]
    [InlineData("\U00011941")]
    [InlineData("\U00011A84")]
    [InlineData("\U00011A89")]
    [InlineData("\U00011D46")]
    [InlineData("\U00011F02")]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void TrailingPropertyCollationMarksCanMoveTheAnnotationSeparator(string suffix)
    {
        var (host, manager, context) = CreateActionCommandContext();
        using (host)
        {
            Issue? actual = null;
            context.Setup(value => value.AddIssue(
                    It.IsAny<Issue>(), It.IsAny<ExecutionContextLogOptions>()))
                .Callback<Issue, ExecutionContextLogOptions>((issue, _) => actual = issue);

            var line = $"::warning title=safe{suffix}::,file=/etc/passwd,line=3::tail";
            Assert.True(manager.TryProcessCommand(context.Object, line, null!));
            Assert.NotNull(actual);
            Assert.Equal("tail", actual!.Message);
            Assert.Equal("etc/passwd", actual.Data["file"]);
            Assert.Equal("3", actual.Data["line"]);
        }
    }

    [Fact]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void AnnotationFilePathsMatchRunnerTranslation()
    {
        var (host, manager, context) = CreateActionCommandContext();
        using (host)
        {
            var issues = new List<Issue>();
            context.Setup(value => value.AddIssue(
                    It.IsAny<Issue>(), It.IsAny<ExecutionContextLogOptions>()))
                .Callback<Issue, ExecutionContextLogOptions>((issue, _) => issues.Add(issue));

            var hostWorkspace = Path.Combine(Path.GetTempPath(), "shoutx-workspace");
            var containerWorkspace = OperatingSystem.IsWindows()
                ? @"C:\container\workspace"
                : "/container/workspace";
            var containerFile = Path.Combine(containerWorkspace, "src", "file.rs");
            var container = new ContainerInfo();
            container.AddPathTranslateMapping(hostWorkspace, containerWorkspace);
            context.Setup(value => value.GetGitHubContext("workspace")).Returns(hostWorkspace);
            context.Setup(value => value.GetGitHubContext("repository")).Returns("owner/repo");

            Assert.True(manager.TryProcessCommand(
                context.Object,
                $"::warning file={EscapeProperty(containerFile)},line=1::container path",
                container));
            var translated = Assert.Single(issues);
            Assert.Equal("src/file.rs", translated.Data["file"]);
            Assert.Equal("owner/repo", translated.Data["repo"]);

            if (OperatingSystem.IsWindows())
            {
                issues.Clear();
                var mixed = @"D:\outside/mixed\file.rs";
                Assert.True(manager.TryProcessCommand(
                    context.Object,
                    $"::warning file={EscapeProperty(mixed)},line=1::mixed path",
                    null!));
                var normalized = Assert.Single(issues);
                Assert.Equal("D:/outside/mixed/file.rs", normalized.Data["file"]);
                Assert.Equal("owner/repo", normalized.Data["repo"]);
            }
        }
    }

    [Fact]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void AnnotationFeatureAndStoppedCommandBehaviorMatchesRunner()
    {
        var corpusPath = Environment.GetEnvironmentVariable("SHOUTX_ANNOTATION_CORPUS");
        var corpus = JsonSerializer.Deserialize<List<AnnotationCase>>(
            File.ReadAllText(corpusPath!),
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!;
        string CommandLine(AnnotationCase item)
        {
            var bytes = Convert.FromBase64String(item.Command);
            return Encoding.UTF8.GetString(bytes, 0, bytes.Length - 1);
        }

        var (host, manager, context) = CreateActionCommandContext();
        using (host)
        {
            Issue? actual = null;
            context.Setup(value => value.AddIssue(
                    It.IsAny<Issue>(), It.IsAny<ExecutionContextLogOptions>()))
                .Callback<Issue, ExecutionContextLogOptions>((issue, _) => actual = issue);
            context.Object.Global.Variables = new Variables(
                host, new Dictionary<string, VariableValue>());

            var noticeLine = CommandLine(corpus.First(item => item.Severity == "notice"));
            Assert.False(manager.TryProcessCommand(context.Object, noticeLine, null!));
            Assert.Null(actual);
            var output = new List<string>();
            context.Setup(value => value.Write(null, It.IsAny<string>()))
                .Callback<string, string>((_, line) => output.Add(line))
                .Returns(1);
            using (var outputManager = new OutputManager(context.Object, manager))
            {
                outputManager.OnDataReceived(
                    null, new ProcessDataReceivedEventArgs(noticeLine));
            }
            Assert.Equal([noticeLine], output);
            Assert.True(manager.TryProcessCommand(
                context.Object, "::warning::warning remains enabled", null!));
            Assert.Equal(IssueType.Warning, actual!.Type);

            actual = null;
            context.Object.Global.Variables = new Variables(
                host, new Dictionary<string, VariableValue>
                {
                    ["DistributedTask.EnhancedAnnotations"] = new VariableValue("true"),
                });
            Assert.True(manager.TryProcessCommand(
                context.Object, "::stop-commands::shoutx-stop-token", null!));
            foreach (var item in corpus
                .GroupBy(value => value.Severity)
                .Select(group => group.First()))
            {
                Assert.False(manager.TryProcessCommand(context.Object, CommandLine(item), null!));
                Assert.Null(actual);
            }
            Assert.True(manager.TryProcessCommand(
                context.Object, "::shoutx-stop-token::", null!));
            Assert.True(manager.TryProcessCommand(
                context.Object, "::error::annotation processing resumed", null!));
            Assert.NotNull(actual);
            Assert.Equal(IssueType.Error, actual!.Type);
            Assert.Equal("annotation processing resumed", actual.Message);
        }
    }

    [Fact]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void IssueToAnnotationConversionDefaultsAndWhitespaceMatchRunner()
    {
        var issue = new Issue
        {
            Type = IssueType.Warning,
            Message = "message",
        };
        issue.Data["file"] = "src/lib.rs";
        issue.Data["line"] = "5";
        issue.Data["col"] = "2";
        issue.Data["title"] = "title";

        var annotation = issue.ToAnnotation();
        Assert.NotNull(annotation);
        var value = annotation!.Value;
        Assert.Equal(5, value.StartLine);
        Assert.Equal(5, value.EndLine);
        Assert.Equal(2, value.StartColumn);
        Assert.Equal(2, value.EndColumn);
        Assert.Equal("src/lib.rs", value.Path);
        Assert.Equal("title", value.Title);

        foreach (var message in new[] { "", " ", "\t", "\u0085", "\u00a0", "\u3000" })
        {
            issue.Message = message;
            Assert.Null(issue.ToAnnotation());
        }
    }

    [Fact]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void RealExecutionContextAppliesAnnotationRetentionPolicies()
    {
        var (host, root) = CreateRealExecutionContext(fixEmbeddedIssues: true);
        using (host)
        {
            host.SecretMasker.AddValue("s");
            var child = root.CreateChild(
                Guid.NewGuid(), "annotations", "annotations", null, null, ActionRunStage.Main);
            child.AddIssue(new Issue
            {
                Type = IssueType.Warning,
                Message = string.Concat(Enumerable.Repeat("s,", 4096)),
            }, ExecutionContextLogOptions.Default);
            for (var index = 0; index < 10; index++)
            {
                child.AddIssue(new Issue
                {
                    Type = IssueType.Warning,
                    Message = $"warning {index}",
                }, ExecutionContextLogOptions.Default);
            }
            child.Complete();

            var result = root.Global.StepsResult.Single();
            Assert.Equal(10, result.Annotations.Count);
            Assert.Equal(4096, result.Annotations[0].Message.Length);
            Assert.StartsWith("***", result.Annotations[0].Message);

            var unmasked = root.CreateChild(
                Guid.NewGuid(), "unmasked", "unmasked", null, null, ActionRunStage.Main);
            unmasked.AddIssue(
                new Issue { Type = IssueType.Error, Message = new string('a', 5000) },
                ExecutionContextLogOptions.Default);
            unmasked.Complete();
            Assert.Equal(4096, root.Global.StepsResult.Last().Annotations.Single().Message.Length);

            var whitespace = root.CreateChild(
                Guid.NewGuid(), "whitespace", "whitespace", null, null, ActionRunStage.Main);
            whitespace.AddIssue(
                new Issue { Type = IssueType.Notice, Message = "\u3000" },
                ExecutionContextLogOptions.Default);
            whitespace.Complete();
            Assert.Empty(root.Global.StepsResult.Last().Annotations);

            var parent = root.CreateChild(
                Guid.NewGuid(), "composite", "composite", null, null, ActionRunStage.Main);
            var embedded = parent.CreateEmbeddedChild(
                "scope", "embedded", Guid.NewGuid(), ActionRunStage.Main);
            embedded.AddIssue(
                new Issue { Type = IssueType.Error, Message = "embedded" },
                ExecutionContextLogOptions.Default);
            embedded.Complete();
            parent.Complete();
            Assert.Contains(
                root.Global.StepsResult.SelectMany(step => step.Annotations),
                annotation => annotation.Message == "embedded");
        }

        var (legacyHost, legacyRoot) = CreateRealExecutionContext(fixEmbeddedIssues: false);
        using (legacyHost)
        {
            var parent = legacyRoot.CreateChild(
                Guid.NewGuid(), "composite", "composite", null, null, ActionRunStage.Main);
            var embedded = parent.CreateEmbeddedChild(
                "scope", "embedded", Guid.NewGuid(), ActionRunStage.Main);
            embedded.AddIssue(
                new Issue { Type = IssueType.Error, Message = "legacy embedded" },
                ExecutionContextLogOptions.Default);
            embedded.Complete();
            parent.Complete();
            Assert.DoesNotContain(
                legacyRoot.Global.StepsResult.SelectMany(step => step.Annotations),
                annotation => annotation.Message == "legacy embedded");
        }
    }

    [Fact]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void AddMaskCommandsMatchRunnerParserAndMasker()
    {
        var corpusPath = Environment.GetEnvironmentVariable("SHOUTX_MASK_CORPUS");
        Assert.False(string.IsNullOrEmpty(corpusPath));
        var corpus = JsonSerializer.Deserialize<List<MaskCase>>(
            File.ReadAllText(corpusPath!),
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
        Assert.NotNull(corpus);

        foreach (var item in corpus!)
        {
            var (host, manager, context) = CreateActionCommandContext();
            using (host)
            {
                var bytes = Convert.FromBase64String(item.Command);
                Assert.Equal((byte)'\n', bytes[^1]);
                var line = Encoding.UTF8.GetString(bytes, 0, bytes.Length - 1);

                Assert.True(manager.TryProcessCommand(context.Object, line, null!));
                Assert.Equal("***", host.SecretMasker.MaskSecrets(Decode(item.Value)));
                foreach (var masked in item.Masked)
                {
                    var value = Decode(masked);
                    Assert.NotEqual(value, host.SecretMasker.MaskSecrets(value));
                }
                foreach (var unmasked in item.Unmasked)
                {
                    var value = Decode(unmasked);
                    Assert.Equal(value, host.SecretMasker.MaskSecrets(value));
                }
            }
        }
    }

    [Fact]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void AddMaskIsIgnoredWhileCommandsAreStopped()
    {
        var (host, manager, context) = CreateActionCommandContext();
        using (host)
        {
            Assert.True(manager.TryProcessCommand(
                context.Object, "::stop-commands::shoutx-stop-token", null!));
            Assert.False(manager.TryProcessCommand(
                context.Object, "::add-mask::secret", null!));
            Assert.Equal("secret", host.SecretMasker.MaskSecrets("secret"));
            Assert.True(manager.TryProcessCommand(
                context.Object, "::shoutx-stop-token::", null!));
            Assert.True(manager.TryProcessCommand(
                context.Object, "::add-mask::secret", null!));
            Assert.Equal("***", host.SecretMasker.MaskSecrets("secret"));
        }
    }

    [Fact]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void AddMaskEchoAndDerivedValuesMatchRunnerBehavior()
    {
        const string secret = "\"alpha beta&+gamma<delta>\"";
        var (host, manager, context) = CreateActionCommandContext();
        using (host)
        {
            // TestHostContext installs only a reduced encoder set. Mirror the
            // production HostContext registrations from Runner.Common here.
            ValueEncoder[] productionEncoders =
            [
                ValueEncoders.Base64StringEscape,
                ValueEncoders.Base64StringEscapeShift1,
                ValueEncoders.Base64StringEscapeShift2,
                ValueEncoders.CommandLineArgumentEscape,
                ValueEncoders.ExpressionStringEscape,
                ValueEncoders.JsonStringEscape,
                ValueEncoders.UriDataEscape,
                ValueEncoders.XmlDataEscape,
                ValueEncoders.TrimDoubleQuotes,
                ValueEncoders.PowerShellPreAmpersandEscape,
                ValueEncoders.PowerShellPostAmpersandEscape,
            ];
            foreach (var encoder in productionEncoders)
            {
                host.SecretMasker.AddValueEncoder(encoder);
            }

            var output = new List<string>();
            context.Object.EchoOnActionCommand = true;
            context.Setup(value => value.Write(It.IsAny<string>(), It.IsAny<string>()))
                .Callback<string, string>((_, message) => output.Add(message))
                .Returns(1);

            Assert.True(manager.TryProcessCommand(
                context.Object, $"::add-mask::{secret}", null!));
            Assert.Equal(["::add-mask::***"], output);
            Assert.DoesNotContain(secret, string.Join("\n", output));

            string[] derived =
            [
                ValueEncoders.Base64StringEscape(secret),
                ValueEncoders.Base64StringEscapeShift1(secret),
                ValueEncoders.Base64StringEscapeShift2(secret),
                ValueEncoders.CommandLineArgumentEscape(secret),
                ValueEncoders.ExpressionStringEscape(secret),
                ValueEncoders.JsonStringEscape(secret),
                ValueEncoders.UriDataEscape(secret),
                ValueEncoders.XmlDataEscape(secret),
                ValueEncoders.TrimDoubleQuotes(secret),
                ValueEncoders.PowerShellPreAmpersandEscape(secret),
                ValueEncoders.PowerShellPostAmpersandEscape(secret),
            ];
            foreach (var value in derived.Where(value => !string.IsNullOrEmpty(value)))
            {
                Assert.NotEqual(value, host.SecretMasker.MaskSecrets(value));
            }
        }
    }

    [Fact]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void MaskedValueTriggersJobOutputSuppressionPredicate()
    {
        var (host, manager, context) = CreateActionCommandContext();
        using (host)
        {
            Assert.True(manager.TryProcessCommand(
                context.Object, "::add-mask::job-output-secret", null!));

            // JobExtension skips an output exactly when MaskSecrets changes it.
            Assert.NotEqual(
                "job-output-secret",
                host.SecretMasker.MaskSecrets("job-output-secret"));
            Assert.Equal("public", host.SecretMasker.MaskSecrets("public"));
        }
    }

    [Fact]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void AddMaskWhitespaceRegistrationMatchesDotNetClassification()
    {
        foreach (var value in new[]
        {
            " ", "\t", "\n", "\u000b", "\f", "\r", "\u0085", "\u00a0", "\u1680",
            "\u2000", "\u2001", "\u2002", "\u2003", "\u2004", "\u2005", "\u2006",
            "\u2007", "\u2008", "\u2009", "\u200a", "\u2028", "\u2029", "\u202f",
            "\u205f", "\u3000",
        })
        {
            var (host, manager, context) = CreateActionCommandContext();
            using (host)
            {
                Assert.True(manager.TryProcessCommand(
                    context.Object, $"::add-mask::{value}", null!));
                Assert.Equal(value, host.SecretMasker.MaskSecrets(value));
            }
        }

        foreach (var value in new[] { "\ufeff", "\u200b" })
        {
            var (host, manager, context) = CreateActionCommandContext();
            using (host)
            {
                Assert.True(manager.TryProcessCommand(
                    context.Object, $"::add-mask::{value}", null!));
                Assert.Equal("***", host.SecretMasker.MaskSecrets(value));
            }
        }
    }

    [Fact]
    [Trait("Level", "L0")]
    [Trait("Category", "Worker")]
    public void StateUsesRunnerCreatedCaseInsensitiveDictionary()
    {
        using var host = new TestHostContext(this);
        Directory.CreateDirectory(host.GetDirectory(WellKnownDirectory.Work));
        var pagingLogger = new Mock<IPagingLogger>();
        var childPagingLogger = new Mock<IPagingLogger>();
        var jobServerQueue = new Mock<IJobServerQueue>();
        jobServerQueue.Setup(x => x.QueueTimelineRecordUpdate(It.IsAny<Guid>(), It.IsAny<TimelineRecord>()));
        host.EnqueueInstance(pagingLogger.Object);
        host.EnqueueInstance(childPagingLogger.Object);
        host.SetSingleton(jobServerQueue.Object);
        var configurationStore = new Mock<IConfigurationStore>();
        configurationStore.Setup(x => x.GetSettings()).Returns(new RunnerSettings());
        host.SetSingleton(configurationStore.Object);

        var jobRequest = new Pipelines.AgentJobRequestMessage(
            new TaskOrchestrationPlanReference(), new TimelineReference(), Guid.NewGuid(),
            "state", "state", null, null, null, new Dictionary<string, VariableValue>(),
            new List<MaskHint>(), new Pipelines.JobResources(),
            new Pipelines.ContextData.DictionaryContextData(), new Pipelines.WorkspaceOptions(),
            new List<Pipelines.ActionStep>(), null, null, null, null, null);
        jobRequest.Resources.Repositories.Add(new Pipelines.RepositoryResource
        {
            Alias = Pipelines.PipelineConstants.SelfAlias,
            Id = "github",
            Version = "sha1",
        });
        jobRequest.ContextData["github"] = new Pipelines.ContextData.DictionaryContextData();

        var root = new Runner.Worker.ExecutionContext();
        root.Initialize(host);
        root.InitializeJob(jobRequest, CancellationToken.None);
        var child = root.CreateChild(
            Guid.NewGuid(), "state", "state", null, null, ActionRunStage.Main);
        var path = Path.GetTempFileName();
        try
        {
            File.WriteAllText(path, "Result=first\nresult=second\n");
            var command = new SaveStateFileCommand();
            command.Initialize(host);
            command.ProcessCommand(child, path, null!);

            Assert.Single(child.IntraActionState);
            Assert.Equal("Result", child.IntraActionState.Keys.Single());
            Assert.Equal("second", child.IntraActionState["RESULT"]);
        }
        finally
        {
            File.Delete(path);
        }
    }

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

    private static string EscapeProperty(string value) => value
        .Replace("%", "%25", StringComparison.Ordinal)
        .Replace("\r", "%0D", StringComparison.Ordinal)
        .Replace("\n", "%0A", StringComparison.Ordinal)
        .Replace(":", "%3A", StringComparison.Ordinal)
        .Replace(",", "%2C", StringComparison.Ordinal);

    private static string Decode(string value) =>
        Encoding.UTF8.GetString(Convert.FromBase64String(value));

    private static (TestHostContext Host, ActionCommandManager Manager, Mock<IExecutionContext> Context)
        CreateActionCommandContext()
    {
        var host = new TestHostContext(
            new ShoutxDifferentialL0(), nameof(CreateActionCommandContext));
        var extensionManager = new Mock<IExtensionManager>();
        IActionCommandExtension[] commands =
        [
            new AddMaskCommandExtension(),
            new NoticeCommandExtension(),
            new WarningCommandExtension(),
            new ErrorCommandExtension(),
        ];
        foreach (var command in commands)
        {
            command.Initialize(host);
        }
        extensionManager.Setup(value => value.GetExtensions<IActionCommandExtension>())
            .Returns(commands.ToList());
        host.SetSingleton<IExtensionManager>(extensionManager.Object);

        var context = new Mock<IExecutionContext>();
        context.SetupAllProperties();
        context.Setup(value => value.Global).Returns(new GlobalContext());
        context.Object.Global.Variables = new Variables(
            host, new Dictionary<string, VariableValue>
            {
                ["DistributedTask.EnhancedAnnotations"] = new VariableValue("true"),
            });
        context.Object.Global.JobTelemetry = [];
        context.Setup(value => value.GetGitHubContext("workspace")).Returns(string.Empty);
        context.Setup(value => value.GetGitHubContext("repository")).Returns(string.Empty);
        var expressionValues = new DictionaryContextData
        {
            ["env"] =
#if OS_WINDOWS
                new DictionaryContextData(),
#else
                new CaseSensitiveDictionaryContextData(),
#endif
        };
        context.Setup(value => value.ExpressionValues).Returns(expressionValues);
        context.Setup(value => value.GetMatchers()).Returns([]);

        var manager = new ActionCommandManager();
        manager.Initialize(host);
        return (host, manager, context);
    }

    private static (TestHostContext Host, Runner.Worker.ExecutionContext Root)
        CreateRealExecutionContext(bool fixEmbeddedIssues)
    {
        var host = new TestHostContext(
            new ShoutxDifferentialL0(), nameof(CreateRealExecutionContext));
        Directory.CreateDirectory(host.GetDirectory(WellKnownDirectory.Work));
        var jobServerQueue = new Mock<IJobServerQueue>();
        jobServerQueue.Setup(x => x.QueueTimelineRecordUpdate(
            It.IsAny<Guid>(), It.IsAny<TimelineRecord>()));
        for (var index = 0; index < 8; index++)
        {
            host.EnqueueInstance(new Mock<IPagingLogger>().Object);
        }
        host.SetSingleton(jobServerQueue.Object);
        var configurationStore = new Mock<IConfigurationStore>();
        configurationStore.Setup(x => x.GetSettings()).Returns(new RunnerSettings());
        host.SetSingleton(configurationStore.Object);

        var variables = new Dictionary<string, VariableValue>
        {
            ["RunService.FixEmbeddedIssues"] = new VariableValue(
                fixEmbeddedIssues ? "true" : "false"),
        };
        var jobRequest = new Pipelines.AgentJobRequestMessage(
            new TaskOrchestrationPlanReference(), new TimelineReference(), Guid.NewGuid(),
            "annotations", "annotations", null, null, null, variables,
            new List<MaskHint>(), new Pipelines.JobResources(),
            new Pipelines.ContextData.DictionaryContextData(), new Pipelines.WorkspaceOptions(),
            new List<Pipelines.ActionStep>(), null, null, null, null, null);
        jobRequest.Resources.Repositories.Add(new Pipelines.RepositoryResource
        {
            Alias = Pipelines.PipelineConstants.SelfAlias,
            Id = "github",
            Version = "sha1",
        });
        jobRequest.ContextData["github"] = new Pipelines.ContextData.DictionaryContextData();

        var root = new Runner.Worker.ExecutionContext();
        root.Initialize(host);
        root.InitializeJob(jobRequest, CancellationToken.None);
        return (host, root);
    }

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
    private sealed record MaskCase(
        string Id,
        string Command,
        string Value,
        IReadOnlyList<string> Masked,
        IReadOnlyList<string> Unmasked);
    private sealed record AnnotationCase(
        string Id,
        string Command,
        string Severity,
        string Message,
        IReadOnlyDictionary<string, string> Properties,
        [property: JsonPropertyName("windows_properties")]
        IReadOnlyDictionary<string, string> WindowsProperties);

    private sealed class ExposedHandler : Handler
    {
        public void ApplyPrependPath() => AddPrependPathToEnvironment();
    }
}
