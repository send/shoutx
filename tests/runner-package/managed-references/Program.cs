using System.Text.Json;

// Offline metadata only. Never load or execute any inspected assembly.
if (args.Length != 1)
{
    Console.Error.WriteLine("Usage: ManagedReferences PACKAGE_BIN");
    return 2;
}
try
{
    var report = ReferenceInventory.Scan(args[0]);
    // Finish the entire inventory before writing any output.
    string json = JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true });
    Console.WriteLine(json);
    return 0;
}
catch (Exception error) when (error is IOException or UnauthorizedAccessException or
    BadImageFormatException or JsonException or KeyNotFoundException or InvalidOperationException or ArgumentException or NotSupportedException)
{
    Console.Error.WriteLine("Managed reference inventory unavailable.");
    return 1;
}
