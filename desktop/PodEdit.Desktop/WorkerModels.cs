using System.Text.Json.Serialization;

namespace PodEdit.Desktop;

public sealed record JobOptions(
    [property: JsonPropertyName("max_duration")] double MaxDuration,
    [property: JsonPropertyName("editorial_profile")] string EditorialProfile,
    [property: JsonPropertyName("offline")] bool Offline = true,
    [property: JsonPropertyName("no_preview")] bool NoPreview = false);

public sealed record WorkerJob(
    [property: JsonPropertyName("schema_version")] int SchemaVersion,
    [property: JsonPropertyName("job_id")] string JobId,
    [property: JsonPropertyName("camera1")] string Camera1,
    [property: JsonPropertyName("camera2")] string Camera2,
    [property: JsonPropertyName("output")] string Output,
    [property: JsonPropertyName("options")] JobOptions Options);

public sealed class WorkerEvent
{
    [JsonPropertyName("event_schema_version")] public int EventSchemaVersion { get; init; }
    [JsonPropertyName("type")] public string Type { get; init; } = "";
    [JsonPropertyName("job_id")] public string JobId { get; init; } = "";
    [JsonPropertyName("message")] public string? Message { get; init; }
    [JsonPropertyName("name")] public string? Name { get; init; }
    [JsonPropertyName("code")] public string? Code { get; init; }
    [JsonPropertyName("progress")] public double? Progress { get; init; }
    [JsonPropertyName("outputs")] public Dictionary<string, object?>? Outputs { get; init; }
    [JsonPropertyName("camera")] public int? Camera { get; init; }
    [JsonPropertyName("width")] public int? Width { get; init; }
    [JsonPropertyName("height")] public int? Height { get; init; }
    [JsonPropertyName("fps")] public double? Fps { get; init; }
    [JsonPropertyName("duration_seconds")] public double? DurationSeconds { get; init; }
}
