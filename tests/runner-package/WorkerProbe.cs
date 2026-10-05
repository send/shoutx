using System.Diagnostics;
using System.Reflection;
using System.Text;
using System.Text.Json;
using GitHub.DistributedTask.WebApi;
using GitHub.DistributedTask.Logging;
using GitHub.Runner.Common;
using GitHub.Runner.Sdk;
using GitHub.Runner.Worker;
using GitHub.Runner.Worker.Handlers;
using Pipelines = GitHub.DistributedTask.Pipelines;
using RunnerContext = GitHub.Runner.Worker.ExecutionContext;

// Strict transport/service doubles only. No parser, command, masker, Write,
// AddIssue or completion implementation is replaced or copied into this probe.
public class ServiceDouble : DispatchProxy
{
    public Func<MethodInfo, object?[], object?> Handler = null!;
    protected override object? Invoke(MethodInfo? method, object?[]? args) => Handler(method!, args!);
    public static T Create<T>(Func<MethodInfo, object?[], object?> handler) where T : class
    {
        T value = Create<T, ServiceDouble>();
        ((ServiceDouble)(object)value).Handler = handler;
        return value;
    }
}

static class WorkerProbe
{
    public static object? CurrentCase;
    static int unexpectedCalls;
    static void Require(bool value, string rule)
    {
        if (!value) throw new ProbeFailure(rule);
    }
    static string Decode(JsonElement item) => Encoding.UTF8.GetString(Convert.FromBase64String(item.GetString()!));
    static string Wire(JsonElement item) => Decode(item.GetProperty("command"))[..^1];
    static object Unexpected(MethodInfo method)
    {
        unexpectedCalls++;
        throw new ProbeFailure("unexpected worker service call: " + method.Name);
    }

    sealed class Fixture : IDisposable
    {
        public readonly SecretMasker Masker = new();
        public readonly List<string> Logs = new();
        readonly List<string> consoleHistory = new();
        readonly Dictionary<Guid, List<string>> pageHistory = new();
        public readonly RunnerContext Root;
        public readonly IExecutionContext Step;
        public readonly OutputManager Output;
        public TimelineRecord Record = null!;
        bool completed;

        public Fixture(Tracing trace)
        {
            // Same production HostContext encoder registrations at the pinned revision.
            foreach (ValueEncoder encoder in new ValueEncoder[] {
                ValueEncoders.Base64StringEscape, ValueEncoders.Base64StringEscapeShift1,
                ValueEncoders.Base64StringEscapeShift2, ValueEncoders.CommandLineArgumentEscape,
                ValueEncoders.ExpressionStringEscape, ValueEncoders.JsonStringEscape,
                ValueEncoders.UriDataEscape, ValueEncoders.XmlDataEscape, ValueEncoders.TrimDoubleQuotes,
                ValueEncoders.PowerShellPreAmpersandEscape, ValueEncoders.PowerShellPostAmpersandEscape })
                Masker.AddValueEncoder(encoder);
            var queue = ServiceDouble.Create<IJobServerQueue>((method, args) => {
                switch (method.Name)
                {
                    case "QueueTimelineRecordUpdate":
                        var record = (TimelineRecord)args[1]!;
                        if (record.RecordType == "Task") Record = record;
                        return null;
                    case "QueueWebConsoleLine":
                        Logs.Add((string)args[1]!);
                        consoleHistory.Add((string)args[1]!);
                        return null;
                    case "add_JobServerQueueThrottling":
                    case "remove_JobServerQueueThrottling": return null;
                    default: return Unexpected(method);
                }
            });
            var config = ServiceDouble.Create<IConfigurationStore>((method, _) =>
                method.Name == "GetSettings" ? new RunnerSettings() : Unexpected(method));
            var commands = new List<IActionCommandExtension> {
                new AddMaskCommandExtension(), new NoticeCommandExtension(),
                new WarningCommandExtension(), new ErrorCommandExtension() };
            var extensions = ServiceDouble.Create<IExtensionManager>((method, _) =>
                method.Name == "GetExtensions" && method.GetGenericArguments().Single() == typeof(IActionCommandExtension)
                    ? commands : Unexpected(method));
            var host = ServiceDouble.Create<IHostContext>((method, _) => {
                if (method.Name == "GetTrace") return trace;
                if (method.Name == "get_SecretMasker") return Masker;
                if (method.Name == "GetService")
                {
                    var type = method.GetGenericArguments().Single();
                    if (type == typeof(IJobServerQueue)) return queue;
                    if (type == typeof(IConfigurationStore)) return config;
                    if (type == typeof(IExtensionManager)) return extensions;
                }
                if (method.Name == "CreateService" && method.GetGenericArguments().Single() == typeof(IPagingLogger))
                {
                    long lines = 0;
                    var writes = new List<string>();
                    return ServiceDouble.Create<IPagingLogger>((call, values) => {
                        switch (call.Name)
                        {
                            case "get_TotalLines": return lines;
                            case "Write":
                                string message = (string)values[0]!;
                                writes.Add(message);
                                lines += 1 + message.Count(c => c == '\n');
                                return null;
                            case "Setup": pageHistory.Add((Guid)values[1]!, writes); return null;
                            case "End": return null;
                            default: return Unexpected(call);
                        }
                    });
                }
                return Unexpected(method);
            });
            foreach (var command in commands) command.Initialize(host);
            Root = new RunnerContext();
            Root.Initialize(host);
            var variables = new Dictionary<string, VariableValue> {
                ["DistributedTask.EnhancedAnnotations"] = new("true") };
            var job = new Pipelines.AgentJobRequestMessage(
                new TaskOrchestrationPlanReference(), new TimelineReference(), Guid.NewGuid(),
                "probe", "probe", null, null, null, variables,
                new List<MaskHint>(), new Pipelines.JobResources(),
                new Pipelines.ContextData.DictionaryContextData(), new Pipelines.WorkspaceOptions(),
                new List<Pipelines.ActionStep>(), null, null, null, null, null);
            job.Resources.Repositories.Add(new Pipelines.RepositoryResource {
                Alias = Pipelines.PipelineConstants.SelfAlias, Id = "github", Version = "synthetic" });
            job.ContextData["github"] = new Pipelines.ContextData.DictionaryContextData {
                ["workspace"] = new Pipelines.ContextData.StringContextData(""),
                ["repository"] = new Pipelines.ContextData.StringContextData("") };
            Root.InitializeJob(job, CancellationToken.None);
            Step = Root.CreateChild(Guid.NewGuid(), "probe", "probe", null, null, ActionRunStage.Main);
            Require(Record is not null, "worker did not queue task record");
            var manager = new ActionCommandManager();
            manager.Initialize(host);
            Output = new OutputManager(Step, manager);
        }

        public void Send(string line)
        {
            Output.OnDataReceived(null, new ProcessDataReceivedEventArgs(line));
            Require(Step.CommandResult is null, "worker extension failed");
            Require(unexpectedCalls == 0, "worker swallowed an unexpected service call");
        }
        public void Complete()
        {
            Require(!completed, "step completed twice");
            Require(Step.Complete() == TaskResult.Succeeded, "annotation changed step result");
            Require(pageHistory[Record.Id].SequenceEqual(consoleHistory), "persisted and console log sinks differ");
            Root.Complete();
            Require(unexpectedCalls == 0, "worker swallowed an unexpected service call");
            completed = true;
        }
        public void Dispose()
        {
            Output.Dispose();
            // Never run/assert additional worker effects while unwinding a failure.
            Masker.Dispose();
        }
    }

    // Research wires intentionally bypass shoutx's acceptance guard. Keep this
    // separate from the producer-generated, current-policy worker corpus below.
    public static object RunUnicode(string tracePath, string expectedCulture)
    {
        unexpectedCalls = 0;
        void CheckCulture() => Require(System.Globalization.CultureInfo.CurrentCulture.Name == expectedCulture,
            "Unicode worker culture changed");
        CheckCulture();
        using var traceMasker = new SecretMasker();
        using var listener = new HostTraceListener(tracePath);
        using var trace = new Tracing("unicode-worker-probe", traceMasker,
            new SourceSwitch("unicode-worker-probe", "Off"), listener);
        static string Escape(string data) => data.Replace("%", "%25").Replace("\r", "%0D").Replace("\n", "%0A");
        string[] tails = { "text", "\u0301\u0327text", "\ufe0f\u200d\U0001f3fbtext",
            "\u0e33\u0eb3text", "##[warning]literal::error::%0A",
            "\r\nsecond-line\n##[error]literal%25::tail" };
        int maskCases = 0, annotationCases = 0, stoppedCases = 0, maskedAnnotationCases = 0;
        foreach (int first in UnicodeCandidateProbe.RepresentativeStarts)
        {
            string prefix = char.ConvertFromUtf32(first);
            for (int tail = 0; tail < tails.Length; tail++)
            {
                string data = prefix + tails[tail];
                foreach (bool echo in new[] { false, true })
                {
                    CurrentCase = new { suite = "unicode-worker-mask", firstScalar = first, tailIndex = tail, echo };
                    using var fixture = new Fixture(trace);
                    fixture.Step.EchoOnActionCommand = echo;
                    fixture.Send("::add-mask::" + Escape(data));
                    Require(fixture.Record.Issues.Count == 0, "Unicode mask created issue");
                    Require(fixture.Logs.SequenceEqual(echo ? new[] { "::add-mask::***" } : Array.Empty<string>()),
                        "Unicode mask command leaked or echo mismatch");
                    Require(fixture.Masker.MaskSecrets(data) == "***", "Unicode full value not masked");
                    // Explicit expectations, including the standalone first-scalar
                    // mask produced by the multiline fixture; no consumer split model.
                    string[] parts = tail == 5 ? new[] { prefix, "second-line", "##[error]literal%25::tail" } : new[] { data };
                    foreach (string part in parts)
                        Require(fixture.Masker.MaskSecrets(part) == "***", "Unicode line mask missing");
                    Require(fixture.Masker.MaskSecrets("literal") == "literal", "Unicode unrelated fragment over-masked");
                    fixture.Logs.Clear();
                    fixture.Step.Write(null, data);
                    Require(fixture.Logs.SequenceEqual(new[] { "***" }), "Unicode subsequent log not redacted");
                    fixture.Complete();
                    maskCases++;
                }
                foreach (string severity in new[] { "notice", "warning", "error" })
                {
                    CurrentCase = new { suite = "unicode-worker-annotation", firstScalar = first, tailIndex = tail, severity };
                    using var fixture = new Fixture(trace);
                    fixture.Step.EchoOnActionCommand = true;
                    fixture.Send($"::{severity} title=ascii,file=src/a.rs,line=5,col=2::" + Escape(data));
                    Require(fixture.Record.Issues.Count == 1, "Unicode annotation issue count mismatch");
                    var issue = fixture.Record.Issues.Single();
                    Require(string.Equals(issue.Type.ToString(), severity, StringComparison.OrdinalIgnoreCase) &&
                        issue.Message == data && issue.Category == "Code", "Unicode annotation content mismatch");
                    var expected = new Dictionary<string, string> { ["title"] = "ascii", ["file"] = "src/a.rs",
                        ["line"] = "5", ["col"] = "2", ["stepNumber"] = "1", ["logFileLineNumber"] = "1" };
                    Require(issue.Data.Count == expected.Count && expected.All(pair =>
                        issue.Data.TryGetValue(pair.Key, out var value) && value == pair.Value), "Unicode annotation properties mismatch");
                    Require(fixture.Logs.SequenceEqual(new[] { $"##[{severity}]{data}" }), "Unicode annotation log mismatch");
                    fixture.Complete();
                    var saved = fixture.Root.Global.StepsResult.Single().Annotations;
                    Require(saved.Count == 1 && saved[0].Message == data && saved[0].Path == "src/a.rs" &&
                        saved[0].Title == "ascii" && saved[0].StartLine == 5 && saved[0].EndLine == 5 &&
                        saved[0].StartColumn == 2 && saved[0].EndColumn == 2 && saved[0].StepNumber == 1 &&
                        saved[0].Level.ToString() == (severity == "error" ? "FAILURE" : severity.ToUpperInvariant()),
                        "Unicode completed annotation mismatch");
                    annotationCases++;
                }
            }
            foreach (string command in new[] { "add-mask", "notice", "warning", "error" })
            {
                CurrentCase = new { suite = "unicode-worker-stop-resume", firstScalar = first, command };
                using var fixture = new Fixture(trace);
                string data = prefix + "\u0301##[warning]literal::tail";
                string wire = $"::{command}::" + Escape(data);
                fixture.Send("::stop-commands::unicode-probe-resume");
                fixture.Logs.Clear();
                fixture.Send(wire);
                Require(fixture.Logs.SequenceEqual(new[] { wire }) && fixture.Record.Issues.Count == 0 &&
                    fixture.Masker.MaskSecrets(data) == data, "stopped Unicode command had side effect");
                fixture.Send("::unicode-probe-wrong-token::");
                fixture.Logs.Clear();
                fixture.Send(wire);
                Require(fixture.Logs.SequenceEqual(new[] { wire }) && fixture.Record.Issues.Count == 0 &&
                    fixture.Masker.MaskSecrets(data) == data, "wrong token resumed Unicode commands");
                fixture.Send("::unicode-probe-resume::");
                fixture.Logs.Clear();
                fixture.Send(wire);
                if (command == "add-mask")
                    Require(fixture.Logs.Count == 0 && fixture.Record.Issues.Count == 0 &&
                        fixture.Masker.MaskSecrets(data) == "***", "resumed Unicode mask mismatch");
                else
                    Require(fixture.Record.Issues.Count == 1 && fixture.Record.Issues[0].Message == data &&
                        fixture.Logs.SequenceEqual(new[] { $"##[{command}]{data}" }), "resumed Unicode annotation mismatch");
                fixture.Complete();
                stoppedCases++;
            }
            CurrentCase = new { suite = "unicode-worker-masked-annotation", firstScalar = first };
            using (var fixture = new Fixture(trace))
            {
                string secret = prefix + "\u0301secret";
                fixture.Send("::add-mask::" + Escape(secret));
                Require(fixture.Logs.Count == 0 && fixture.Record.Issues.Count == 0, "Unicode mask leaked before annotation");
                fixture.Send("::warning::" + Escape(secret + " after"));
                Require(fixture.Logs.SequenceEqual(new[] { "##[warning]*** after" }), "Unicode annotation not redacted");
                fixture.Complete();
                var saved = fixture.Root.Global.StepsResult.Single().Annotations;
                Require(saved.Count == 1 && saved[0].Message == "*** after", "Unicode completed annotation not redacted");
                maskedAnnotationCases++;
            }
            CheckCulture();
        }
        int negativeControlCases = 0;
        foreach (int first in new[] { 0x301, 0xe33 })
        {
            CurrentCase = new { suite = "unicode-worker-negative-control", firstScalar = first };
            using var fixture = new Fixture(trace);
            string data = char.ConvertFromUtf32(first) + "synthetic-value ##[warning]fallback";
            fixture.Send("::add-mask::" + data);
            Require(fixture.Record.Issues.Count == 1 && fixture.Record.Issues[0].Type == IssueType.Warning &&
                fixture.Record.Issues[0].Message == "fallback" && fixture.Masker.MaskSecrets(data) == data &&
                fixture.Logs.SequenceEqual(new[] { "##[warning]fallback" }), "Unicode negative control did not select fallback");
            fixture.Complete();
            Require(fixture.Root.Global.StepsResult.Single().Annotations.Single().Message == "fallback",
                "Unicode negative control completion mismatch");
            negativeControlCases++;
            CheckCulture();
        }
        Require(unexpectedCalls == 0, "Unicode worker swallowed an unexpected service call");
        return new { researchOnly = true, observedCulture = System.Globalization.CultureInfo.CurrentCulture.Name,
            maskCases, annotationCases, stoppedCases, maskedAnnotationCases, negativeControlCases };
    }

    public static object Run(string maskPath, string annotationPath, string tracePath)
    {
        unexpectedCalls = 0;
        using var traceMasker = new SecretMasker();
        using var listener = new HostTraceListener(tracePath);
        using var trace = new Tracing("package-worker-probe", traceMasker,
            new SourceSwitch("package-worker-probe", "Off"), listener);
        using var masks = JsonDocument.Parse(File.ReadAllBytes(maskPath));
        using var annotations = JsonDocument.Parse(File.ReadAllBytes(annotationPath));
        int maskCases = 0, annotationCases = 0;
        foreach (var item in masks.RootElement.EnumerateArray())
        {
            CurrentCase = new { suite = "worker-mask", index = maskCases };
            using var fixture = new Fixture(trace);
            fixture.Send(Wire(item));
            Require(fixture.Logs.Count == 0 && fixture.Record.Issues.Count == 0, "mask command leaked or created issue");
            Require(fixture.Masker.MaskSecrets(Decode(item.GetProperty("value"))) == "***", "full value not masked");
            foreach (var value in item.GetProperty("masked").EnumerateArray())
                Require(fixture.Masker.MaskSecrets(Decode(value)) != Decode(value), "derived mask missing");
            foreach (var value in item.GetProperty("unmasked").EnumerateArray())
                Require(fixture.Masker.MaskSecrets(Decode(value)) == Decode(value), "unexpected derived mask");
            fixture.Step.Write(null, Decode(item.GetProperty("value")));
            Require(fixture.Logs.SequenceEqual(new[] { "***" }), "subsequent log not redacted");
            fixture.Complete();
            maskCases++;
        }
        foreach (var item in annotations.RootElement.EnumerateArray())
        {
            CurrentCase = new { suite = "worker-annotation", index = annotationCases };
            using var fixture = new Fixture(trace);
            fixture.Step.EchoOnActionCommand = true;
            fixture.Send(Wire(item));
            Require(fixture.Record.Issues.Count == 1, "annotation issue count mismatch");
            var issue = fixture.Record.Issues.Single();
            string message = Decode(item.GetProperty("message"));
            string severity = item.GetProperty("severity").GetString()!;
            Require(string.Equals(issue.Type.ToString(), severity, StringComparison.OrdinalIgnoreCase), "annotation severity mismatch");
            Require(issue.Message == message, "annotation message mismatch");
            var properties = item.GetProperty(OperatingSystem.IsWindows() ? "windows_properties" : "properties");
            Require(issue.Category == (properties.TryGetProperty("file", out _) ? "Code" : "General"), "annotation category mismatch");
            Require(issue.Data.Count == properties.EnumerateObject().Count() + 2, "annotation property count mismatch");
            foreach (var property in properties.EnumerateObject())
                Require(issue.Data.TryGetValue(property.Name, out var value) && value == Decode(property.Value), "annotation property mismatch");
            Require(issue.Data["stepNumber"] == "1" && issue.Data["logFileLineNumber"] == "1", "annotation provenance mismatch");
            Require(fixture.Logs.SequenceEqual(new[] { $"##[{severity}]{message}" }), "annotation log or echo mismatch");
            fixture.Complete();
            var saved = fixture.Root.Global.StepsResult.Single().Annotations;
            Require(saved.Count == 1 && saved[0].Message == message, "completion annotation mismatch");
            annotationCases++;
        }
        int stoppedCases = 0;
        foreach (string command in new[] { "add-mask", "notice", "warning", "error" })
        {
            CurrentCase = new { suite = "worker-stop-resume", command };
            using var fixture = new Fixture(trace);
            const string secret = "probe-secret-ASCII";
            string wire = $"::{command}::{secret}";
            fixture.Send("::stop-commands::package-probe-resume-token");
            Require(fixture.Logs.SequenceEqual(new[] { "::stop-commands::***" }), "stop token echo not masked");
            fixture.Logs.Clear();
            fixture.Send(wire);
            Require(fixture.Logs.SequenceEqual(new[] { wire }), "stopped command not logged literally");
            Require(fixture.Record.Issues.Count == 0 && fixture.Masker.MaskSecrets(secret) == secret, "stopped command had side effect");
            fixture.Send("::package-probe-wrong-token::");
            fixture.Logs.Clear();
            fixture.Send(wire);
            Require(fixture.Logs.SequenceEqual(new[] { wire }) && fixture.Record.Issues.Count == 0 && fixture.Masker.MaskSecrets(secret) == secret,
                "wrong token resumed commands");
            fixture.Send("::package-probe-resume-token::");
            Require(fixture.Logs.Last() == "::***::", "resume token echo not masked");
            fixture.Logs.Clear();
            fixture.Send(wire);
            if (command == "add-mask")
            {
                Require(fixture.Logs.Count == 0 && fixture.Record.Issues.Count == 0, "resumed mask leaked");
                fixture.Step.Write(null, secret);
                Require(fixture.Logs.SequenceEqual(new[] { "***" }), "resumed mask not applied");
            }
            else
                Require(fixture.Record.Issues.Count == 1 && fixture.Record.Issues[0].Message == secret &&
                    fixture.Logs.SequenceEqual(new[] { $"##[{command}]{secret}" }), "resumed annotation missing");
            fixture.Complete();
            stoppedCases++;
        }
        CurrentCase = new { suite = "worker-echo-and-masked-annotation" };
        using (var fixture = new Fixture(trace))
        {
            fixture.Step.EchoOnActionCommand = true;
            fixture.Send("::add-mask::probe-sensitive");
            Require(fixture.Logs.SequenceEqual(new[] { "::add-mask::***" }), "mask echo revealed value");
            fixture.Logs.Clear();
            fixture.Send("::warning title=title,file=src/a.rs,line=5,col=2::before probe-sensitive after");
            Require(fixture.Logs.SequenceEqual(new[] { "##[warning]before *** after" }), "annotation redaction mismatch");
            fixture.Complete();
            var saved = fixture.Root.Global.StepsResult.Single().Annotations.Single();
            Require(saved.Message == "before *** after" && saved.Path == "src/a.rs" && saved.Title == "title" &&
                saved.StartLine == 5 && saved.EndLine == 5 && saved.StartColumn == 2 && saved.EndColumn == 2,
                "masked completion annotation mismatch");
        }
        Require(maskCases > 0 && annotationCases > 0, "empty worker corpus");
        Require(unexpectedCalls == 0, "worker swallowed an unexpected service call");
        return new { maskCases, annotationCases, stoppedCases, echoAndMaskedAnnotationCases = 1 };
    }
}
