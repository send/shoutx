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
        result["searchCollatorMatches"] = api.GetCollator(search) == collator;
        Require(result["searchCollatorMatches"] is true, "search uses a different collator");
        var attributes = new Dictionary<string, int>();
        result["collatorAttributes"] = attributes;
        string[] attributeNames = { "french", "alternate", "caseFirst", "caseLevel", "normalization", "strength", "hiragana", "numeric" };
        for (int index = 0; index < attributeNames.Length; index++)
        {
            int error = 0;
            attributes[attributeNames[index]] = api.CollatorAttribute(collator, index, ref error);
            Check(error);
        }
        int comparison = api.SearchAttribute(search, 2); // USEARCH_ELEMENT_COMPARISON
        result["searchElementComparison"] = comparison;
        // Public USEARCH_STANDARD_ELEMENT_COMPARISON is 2; the internal
        // elementComparisonType field described by usearch.cpp uses zero.
        Require(comparison == 2 && attributes["strength"] == 2 && attributes["alternate"] == 21 &&
            attributes.Where(p => p.Key is not ("strength" or "alternate")).All(p => p.Value == 16),
            "unreviewed collator/search settings");
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
        ObserveOffsets(api, collator, compare, table.RootElement, emptyEquivalent, emptyExamples, result);
        GC.KeepAlive(compare); // Do not close or mutate borrowed native handles.
        result["status"] = "passed";
    }

    readonly record struct Element(int value, int low, int high);
    static bool ZeroWidth(Element element) => element.low == element.high;

    static void ObserveOffsets(Api api, IntPtr collator, CompareInfo compare, JsonElement table,
        int emptyCount, List<int> emptyExamples, Dictionary<string, object?> result)
    {
        var timer = Stopwatch.StartNew();
        var observation = new Dictionary<string, object?> { ["status"] = "incomplete", ["researchOnly"] = true };
        result["ceOffsets"] = observation;
        int[] prefixes = { 0x0640, 0x07fa, 0x180a, 0x1cd3, 0xfe73 };
        observation["prefixes"] = prefixes;
        Require(emptyCount == prefixes.Length && emptyExamples.SequenceEqual(prefixes),
            "offset suite empty-equivalent set changed");
        var baseline = api.Elements(collator, "::x");
        Require(baseline.Count >= 3 && baseline[0].low == 0 && baseline[0].high == 1 &&
            baseline[1].low == 1 && baseline[1].high == 2 && baseline[0].value != 0 &&
            baseline[0].value == baseline[1].value, "unexpected colon elements");
        int candidateChecks = 0, pairChecks = 0, delimiterFailures = 0, zeroWidthNext = 0, separatorFailures = 0, skippedZeroCases = 0;
        var examples = new List<object>();
        void Inspect(string data, int first, int? second)
        {
            // Finite test shape only: data always ends in literal x. An owned
            // iterator observes :: + data, while CompareInfo searches a full
            // warning header with a later delimiter to expose skipped matches.
            var elements = api.Elements(collator, "::" + data);
            bool delimiter = elements.Count >= 3 && elements[0] == baseline[0] && elements[1] == baseline[1];
            int nextIndex = elements.Count >= 3 ? elements.FindIndex(2, e => e.value != 0) : -1;
            if (nextIndex < 0)
                observation["failedCase"] = new { first, second, elements, candidateChecks, pairChecks };
            Require(nextIndex >= 0, "offset suite missing terminal x element");
            var next = elements[nextIndex];
            bool zeroWidth = ZeroWidth(next);
            if (nextIndex > 2) skippedZeroCases++;
            int separator = compare.IndexOf("::warning::" + data + "::later", "::", 2, CompareOptions.None);
            if (!delimiter || next.low < 2) delimiterFailures++;
            if (zeroWidth) zeroWidthNext++;
            if (separator != 9) separatorFailures++;
            if ((!delimiter || next.low < 2 || zeroWidth || separator != 9) && examples.Count < 16)
                examples.Add(new { first, second, next, separator });
        }
        foreach (var range in table.GetProperty("ranges").EnumerateArray())
        for (int cp = range[0].GetInt32(); cp <= range[1].GetInt32(); cp++)
        {
            Inspect(char.ConvertFromUtf32(cp) + "x", cp, null);
            candidateChecks++;
        }
        foreach (int prefix in prefixes)
        for (int cp = 1; cp <= 0x10ffff; cp++)
        {
            if (cp is >= 0xd800 and <= 0xdfff) continue;
            Inspect(char.ConvertFromUtf32(prefix) + char.ConvertFromUtf32(cp) + "x", prefix, cp);
            pairChecks++;
        }
        var samples = new List<object>();
        observation["samples"] = samples; // Keep the failing sample if a Require below throws.
        foreach (string data in new[] { "日", "😀", "\u0640x", "\u07fax", "\u180ax", "\u1cd3x", "\ufe73x", "\u0640\u0301", "\u0301" })
        {
            int separator = compare.IndexOf("::warning::" + data + "::later", "::", 2, CompareOptions.None);
            var elements = api.Elements(collator, "::" + data);
            samples.Add(new { data, elements, separator });
            Require(elements.Count >= 3 && elements[0] == baseline[0] && elements[1] == baseline[1], "sample delimiter elements");
            int nextIndex = elements.FindIndex(2, e => e.value != 0);
            Require(nextIndex >= 0 && elements[nextIndex].low >= 2 && !ZeroWidth(elements[nextIndex]), "sample retained element");
            if (prefixes.Contains(data[0])) Require(elements[2] == new Element(0, 2, 3), "sample raw-zero prefix");
            Require(separator == (data == "\u0301" ? 12 : 9), "offset sample/control mismatch");
        }
        // A real canonical expansion supplies a zero-width nonzero second CE.
        // Reuse the same detector, then independently observe rejection of the
        // partial 'a' match in å, followed by acceptance of the literal a.
        var expansion = api.Elements(collator, "\u00e5a");
        int expansionIndex = compare.IndexOf("\u00e5a", "a", CompareOptions.None);
        observation["expansionControl"] = new { text = "\u00e5a", pattern = "a", elements = expansion, index = expansionIndex };
        Require(expansion.Count == 3 && expansion[0].low == 0 && expansion[0].high == 1 && expansion[0].value != 0 &&
            expansion[1].low == 1 && ZeroWidth(expansion[1]) && expansion[1].value != 0 &&
            expansion[2].low == 1 && expansion[2].high == 2 && expansion[2].value == expansion[0].value && expansionIndex == 1,
            "partial-expansion control mismatch");
        observation["candidateChecks"] = candidateChecks;
        observation["pairChecks"] = pairChecks;
        observation["delimiterFailures"] = delimiterFailures;
        observation["zeroWidthNextCount"] = zeroWidthNext;
        observation["separatorFailures"] = separatorFailures;
        observation["skippedZeroCases"] = skippedZeroCases;
        observation["elapsedMilliseconds"] = timer.ElapsedMilliseconds;
        observation["examples"] = examples;
        Require(candidateChecks == 142081 && pairChecks == 5560315 && delimiterFailures == 0 &&
            zeroWidthNext == 0 && separatorFailures == 0 && skippedZeroCases > 0, "finite CE-offset hypothesis failed");
        observation["status"] = "passed";
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
        public readonly PointerArg GetCollator;
        public readonly GetAttribute CollatorAttribute;
        public readonly SearchGetAttribute SearchAttribute;
        readonly OpenElements OpenElementIterator;
        readonly ClosePointer CloseElements;
        readonly CountItems ElementOffset;
        readonly NextElement Next;

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
                GetCollator = Bind<PointerArg>(international, "usearch_getCollator");
                CollatorAttribute = Bind<GetAttribute>(international, "ucol_getAttribute");
                SearchAttribute = Bind<SearchGetAttribute>(international, "usearch_getAttribute");
                OpenElementIterator = Bind<OpenElements>(international, "ucol_openElements");
                CloseElements = Bind<ClosePointer>(international, "ucol_closeElements");
                ElementOffset = Bind<CountItems>(international, "ucol_getOffset");
                Next = Bind<NextElement>(international, "ucol_next");
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
        public List<Element> Elements(IntPtr collator, string text)
        {
            // Keep the UTF-16 buffer valid even if ICU retains its pointer.
            // Pin explicitly across all calls; do not rely on call-only string
            // marshalling. Borrowed runtime collator/search objects stay intact.
            var pinned = GCHandle.Alloc(text, GCHandleType.Pinned);
            IntPtr iterator = IntPtr.Zero;
            try
            {
                int error = 0;
                iterator = OpenElementIterator(collator, pinned.AddrOfPinnedObject(), text.Length, ref error);
                Check(error);
                Require(iterator != IntPtr.Zero, "CE iterator unavailable");
                var elements = new List<Element>();
                for (int count = 0; count < 128; count++)
                {
                    int low = ElementOffset(iterator);
                    int value = Next(iterator, ref error);
                    Check(error);
                    int high = ElementOffset(iterator);
                    Require(low >= 0 && low <= high && high <= text.Length, "invalid CE offset");
                    if (value == -1) return elements; // UCOL_NULLORDER
                    elements.Add(new Element(value, low, high));
                }
                throw new ProbeFailure("CE observation bound exceeded");
            }
            finally
            {
                if (iterator != IntPtr.Zero) CloseElements(iterator);
                pinned.Free();
            }
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
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate int GetAttribute(IntPtr collator, int attribute, ref int error);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)] public delegate int SearchGetAttribute(IntPtr search, int attribute);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr OpenElements(IntPtr collator, IntPtr text, int length, ref int error);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int NextElement(IntPtr iterator, ref int error);
    }
}
