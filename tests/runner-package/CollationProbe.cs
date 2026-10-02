using System.Diagnostics;
using System.Globalization;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;

// Research-only private-layout observation, never linked into shoutx. Do not
// broaden the runtime/architecture guard without reviewing pal_collation.c.
static class CollationProbe
{
    static void Require(bool value, string rule) { if (!value) throw new ProbeFailure(rule); }
    static void Check(int error) => Require(error <= 0, "ICU observation API failed");
    static string Hash(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
    static byte[] Resource(string name)
    {
        using var stream = typeof(CollationProbe).Assembly.GetManifestResourceStream(name)
            ?? throw new ProbeFailure("missing collation resource");
        using var bytes = new MemoryStream();
        stream.CopyTo(bytes);
        return bytes.ToArray();
    }

    public static void Run(Dictionary<string, object?> result, uint expectedVersion, bool preconditions)
    {
        result["status"] = "incomplete";
        result["researchOnly"] = true;
        Require(preconditions && expectedVersion != 0, "ICU observation preconditions unavailable");
        Require(IntPtr.Size == 8 && RuntimeInformation.ProcessArchitecture is Architecture.X64 or Architecture.Arm64 &&
            typeof(object).Assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion ==
                "8.0.30+a83db3e0eb2defb6220e15dae2f1a0462fdbf99f", "unreviewed native sort handle layout");
        var compare = CultureInfo.CurrentCulture.CompareInfo;
        result["culture"] = compare.Name;
        Require(compare.IndexOf("::warning::日text", "::", 2, CompareOptions.None) == 9, "native observation separator mismatch");
        using var api = new Api(expectedVersion, result);
        // Single-threaded probe only. The native layout begins with 32 collator
        // pointers, then 32 (searchIterator,next) pairs. Observe option zero.
        var field = typeof(CompareInfo).GetField("_sortHandle", BindingFlags.NonPublic | BindingFlags.Instance);
        Require(field?.GetValue(compare) is IntPtr, "native sort handle unavailable");
        var handle = (IntPtr)field!.GetValue(compare)!;
        Require(handle != IntPtr.Zero, "empty native sort handle");
        var collator = Marshal.ReadIntPtr(handle);
        var search = Marshal.ReadIntPtr(handle, 32 * IntPtr.Size);
        Require(collator != IntPtr.Zero && search != IntPtr.Zero && search != new IntPtr(-1), "native cache slot unavailable");
        var breaker = api.GetBreaker(search);
        result["externalBreakIterator"] = breaker != IntPtr.Zero;
        Require(breaker != IntPtr.Zero, "internal break iterator fallback observed");
        string actualHash = api.RuleHash(breaker);
        result["actualRuleSha256"] = actualHash;
        byte[] ruleBytes = Resource("break-rules.json");
        result["ruleResourceSha256"] = Hash(ruleBytes);
        using var rules = JsonDocument.Parse(ruleBytes);
        result["ruleSourceSha256"] = rules.RootElement.GetProperty("sourceSha256").GetString();
        var compiled = new Dictionary<string, object?>();
        result["compiledRules"] = compiled;
        string selected = "unknown";
        foreach (string name in new[] { "new", "old" })
        {
            string text = rules.RootElement.GetProperty(name).GetString()!;
            int error = 0;
            var owned = api.OpenRules(text, text.Length, IntPtr.Zero, 0, IntPtr.Zero, ref error);
            string? hash = null;
            try { if (error <= 0 && owned != IntPtr.Zero) hash = api.RuleHash(owned); }
            finally { if (owned != IntPtr.Zero) api.CloseBreaker(owned); }
            compiled[name] = new { error, sha256 = hash };
            if (hash == actualHash) { Require(selected == "unknown", "ambiguous compiled rules"); selected = name; }
        }
        result["selectedRules"] = selected;
        Require(selected == "new", "new custom break rules not observed");

        var set = api.OpenSet();
        Require(set != IntPtr.Zero, "ICU context set unavailable");
        int colonContexts = 0;
        try
        {
            int error = 0;
            api.Contexts(collator, set, IntPtr.Zero, 1, ref error); // Include prefix contexts.
            Check(error);
            int count = api.ItemCount(set);
            Require(count > 0 && count <= 100000, "unexpected ICU context count");
            result["contextItemCount"] = count;
            for (int index = 0; index < count; index++)
            {
                ushort[] buffer = new ushort[4096];
                error = 0;
                int size = api.Item(set, index, out int start, out int end, buffer, buffer.Length, ref error);
                Check(error);
                Require(size >= 0 && size <= buffer.Length, "invalid ICU context length");
                if (size == 0 ? start <= 58 && end >= 58 : buffer.Take(size).Contains((ushort)58)) colonContexts++;
            }
            result["contextChecks"] = count;
        }
        finally { api.CloseSet(set); }
        result["colonContextCount"] = colonContexts;

        byte[] tableBytes = Resource("unicode-candidate.json");
        using var table = JsonDocument.Parse(tableBytes);
        result["tableSha256"] = Hash(tableBytes);
        int nfdError = 0;
        var nfd = api.Nfd(ref nfdError);
        Check(nfdError);
        Require(nfd != IntPtr.Zero, "NFD observer unavailable");
        int checkedScalars = 0, missingNfd = 0, unexpectedGcb = 0, emptyEquivalent = 0;
        var emptyExamples = new List<int>();
        foreach (var range in table.RootElement.GetProperty("ranges").EnumerateArray())
        for (int cp = range[0].GetInt32(); cp <= range[1].GetInt32(); cp++)
        {
            checkedScalars++;
            if (api.BoundaryBefore(nfd, cp) == 0) missingNfd++;
            if (api.Property(cp, 0x1012) is not (0 or 4 or 6 or 7 or 8 or 9 or 12)) unexpectedGcb++;
            if (compare.Compare(char.ConvertFromUtf32(cp), "", CompareOptions.None) == 0)
            {
                emptyEquivalent++;
                if (emptyExamples.Count < 16) emptyExamples.Add(cp);
            }
        }
        result["scalarChecks"] = checkedScalars;
        result["missingNfdBoundaryCount"] = missingNfd;
        result["unexpectedGcbCount"] = unexpectedGcb;
        result["emptyEquivalentCount"] = emptyEquivalent;
        result["emptyEquivalentExamples"] = emptyExamples;
        Require(checkedScalars == 142081 && colonContexts == 0 && missingNfd == 0 && unexpectedGcb == 0,
            "collation boundary hypothesis failed");
        GC.KeepAlive(compare); // Do not close or mutate borrowed native handles.
        result["status"] = "passed";
    }

    sealed class Api : IDisposable
    {
        readonly List<IntPtr> ownedModules = new();
        readonly IntPtr common, international;
        readonly string suffix;
        public readonly PointerArg GetBreaker;
        public readonly BinaryRules Binary;
        public readonly OpenBreakRules OpenRules;
        public readonly ClosePointer CloseBreaker, CloseSet;
        public readonly OpenPointer OpenSet;
        public readonly GetContexts Contexts;
        public readonly CountItems ItemCount;
        public readonly GetItem Item;
        public readonly GetNfd Nfd;
        public readonly Before BoundaryBefore;
        public readonly GetProperty Property;

        public Api(uint expectedVersion, Dictionary<string, object?> result)
        {
            try
            {
                string commonPath, internationalPath;
                if (OperatingSystem.IsMacOS())
                {
                    commonPath = internationalPath = "/usr/lib/libicucore.A.dylib";
                    common = international = MacOpen(commonPath, 0x11); // LAZY | NOLOAD
                    if (common != IntPtr.Zero) ownedModules.Add(common);
                    suffix = "";
                }
                else
                {
                    using var process = Process.GetCurrentProcess();
                    var paths = process.Modules.Cast<ProcessModule>().Select(m => m.FileName).Distinct().ToArray();
                    string Single(string pattern)
                    {
                        var matches = paths.Where(p => System.Text.RegularExpressions.Regex.IsMatch(Path.GetFileName(p), pattern,
                            System.Text.RegularExpressions.RegexOptions.IgnoreCase)).ToArray();
                        Require(matches.Length == 1, "ambiguous or unavailable loaded ICU module");
                        return matches[0];
                    }
                    if (OperatingSystem.IsLinux())
                    {
                        commonPath = Single(@"^libicuuc\.so\.[0-9.]+$");
                        internationalPath = Single(@"^libicui18n\.so\.[0-9.]+$");
                        common = LinuxOpen(commonPath, 5); // LAZY | NOLOAD
                        if (common != IntPtr.Zero) ownedModules.Add(common);
                        international = LinuxOpen(internationalPath, 5);
                        if (international != IntPtr.Zero) ownedModules.Add(international);
                        suffix = "_" + (expectedVersion >> 24).ToString(CultureInfo.InvariantCulture);
                    }
                    else if (OperatingSystem.IsWindows())
                    {
                        bool combined = paths.Any(p => Path.GetFileName(p).Equals("icu.dll", StringComparison.OrdinalIgnoreCase));
                        commonPath = Single(combined ? @"^icu\.dll$" : @"^icuuc\.dll$");
                        internationalPath = combined ? commonPath : Single(@"^icuin\.dll$");
                        common = GetModuleHandle(commonPath);
                        international = GetModuleHandle(internationalPath); // Borrowed; never FreeLibrary.
                        suffix = "";
                    }
                    else throw new ProbeFailure("unsupported native observation OS");
                }
                Require(common != IntPtr.Zero && international != IntPtr.Zero, "loaded ICU handle unavailable");
                result["commonLibrary"] = commonPath;
                result["internationalLibrary"] = internationalPath;
                result["symbolSuffix"] = suffix;
                byte[] version = new byte[4];
                Bind<Version>(common, "u_getVersion")(version);
                uint raw = ((uint)version[0] << 24) | ((uint)version[1] << 16) | ((uint)version[2] << 8) | version[3];
                Require(raw == expectedVersion, "loaded ICU version differs from CoreLib");
                result["icuVersionRaw"] = raw;
                GetBreaker = Bind<PointerArg>(international, "usearch_getBreakIterator");
                Binary = Bind<BinaryRules>(common, "ubrk_getBinaryRules");
                OpenRules = Bind<OpenBreakRules>(common, "ubrk_openRules");
                CloseBreaker = Bind<ClosePointer>(common, "ubrk_close");
                OpenSet = Bind<OpenPointer>(common, "uset_openEmpty");
                CloseSet = Bind<ClosePointer>(common, "uset_close");
                Contexts = Bind<GetContexts>(international, "ucol_getContractionsAndExpansions");
                ItemCount = Bind<CountItems>(common, "uset_getItemCount");
                Item = Bind<GetItem>(common, "uset_getItem");
                Nfd = Bind<GetNfd>(common, "unorm2_getNFDInstance");
                BoundaryBefore = Bind<Before>(common, "unorm2_hasBoundaryBefore");
                Property = Bind<GetProperty>(common, "u_getIntPropertyValue");
            }
            catch { Dispose(); throw; }
        }
        T Bind<T>(IntPtr module, string name) where T : Delegate
        {
            Require(NativeLibrary.TryGetExport(module, name + suffix, out var address), "required ICU export unavailable");
            return Marshal.GetDelegateForFunctionPointer<T>(address);
        }
        public string RuleHash(IntPtr breaker)
        {
            byte[] bytes = new byte[262144];
            int error = 0;
            int count = Binary(breaker, bytes, bytes.Length, ref error);
            Check(error);
            Require(count > 0 && count <= bytes.Length, "invalid ICU binary rule length");
            return Hash(bytes[..count]);
        }
        public void Dispose()
        {
            foreach (var module in ownedModules) NativeLibrary.Free(module);
            ownedModules.Clear();
        }
        [DllImport("/usr/lib/libSystem.B.dylib", EntryPoint = "dlopen")] static extern IntPtr MacOpen(string path, int flags);
        [DllImport("libdl.so.2", EntryPoint = "dlopen")] static extern IntPtr LinuxOpen(string path, int flags);
        [DllImport("kernel32.dll", EntryPoint = "GetModuleHandleW", CharSet = CharSet.Unicode)] static extern IntPtr GetModuleHandle(string path);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate void Version([Out] byte[] value);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate IntPtr PointerArg(IntPtr value);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate IntPtr OpenPointer();
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate void ClosePointer(IntPtr value);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate int CountItems(IntPtr value);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate int BinaryRules(IntPtr value, [Out] byte[] bytes, int length, ref int error);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate IntPtr OpenBreakRules([MarshalAs(UnmanagedType.LPWStr)] string rules, int length, IntPtr text, int textLength, IntPtr parseError, ref int error);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate void GetContexts(IntPtr collator, IntPtr contractions, IntPtr expansions, sbyte prefixes, ref int error);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate int GetItem(IntPtr set, int index, out int start, out int end, [Out] ushort[] buffer, int length, ref int error);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate IntPtr GetNfd(ref int error);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate sbyte Before(IntPtr nfd, int cp);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate int GetProperty(int cp, int property);
    }
}
