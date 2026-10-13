using System.IO;
using System.Text.Json;

namespace PodEdit.Desktop;

public sealed record UiState(string Camera1, string Camera2, string Output,
                             string Minutes, string EditorialProfile, bool RenderPreview);

public static class UiStateStore
{
    public static UiState? Load(DirectoryInfo projectRoot)
    {
        var path = StatePath(projectRoot);
        try { return JsonSerializer.Deserialize<UiState>(File.ReadAllText(path)); }
        catch (IOException) { return null; }
        catch (JsonException) { return null; }
    }

    public static void Save(DirectoryInfo projectRoot, UiState state)
    {
        var path = StatePath(projectRoot);
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var temporary = path + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(state,
            new JsonSerializerOptions { WriteIndented = true }));
        File.Move(temporary, path, overwrite: true);
    }

    private static string StatePath(DirectoryInfo root)
    {
        if (File.Exists(Path.Combine(root.FullName, "PodEdit.Worker.exe"))) {
            var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            return Path.Combine(local, "PodEdit", "settings", "last-job.json");
        }
        return Path.Combine(root.FullName, ".desktop_state", "last-job.json");
    }
}
