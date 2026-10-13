using PodEdit.Desktop;
using System.Text.Json;

var job = new WorkerJob(1, "contract-check", @"C:\media\camera one.mp4",
    @"C:\media\cámara two.mp4", @"C:\exports\episode",
    new JobOptions(1500, "balanced", Offline: true, NoPreview: false));
var json = JsonSerializer.Serialize(job);
using var document = JsonDocument.Parse(json);
var root = document.RootElement;
Require(root.GetProperty("schema_version").GetInt32() == 1, "job schema");
Require(root.GetProperty("camera1").GetString()!.EndsWith("camera one.mp4"), "space path");
Require(root.GetProperty("options").GetProperty("max_duration").GetDouble() == 1500, "duration");
Require(root.GetProperty("options").GetProperty("offline").GetBoolean(), "offline flag");

var workerEvent = JsonSerializer.Deserialize<WorkerEvent>(
    """{"event_schema_version":1,"type":"stage_started","job_id":"contract-check","name":"DIARIZATION","progress":0.5}""");
Require(workerEvent?.Type == "stage_started", "event type");
Require(workerEvent?.Progress == 0.5, "event progress");
var source = JsonSerializer.Deserialize<WorkerEvent>(
    """{"event_schema_version":1,"type":"source_inspected","job_id":"contract-check","camera":2,"width":1280,"height":720,"fps":29.97,"duration_seconds":1500}""");
Require(source?.Camera == 2 && source.Width == 1280 && source.DurationSeconds == 1500,
        "source metadata");
var artifacts = JsonSerializer.Deserialize<WorkerEvent>(
    """{"event_schema_version":1,"type":"artifacts_available","job_id":"contract-check","outputs":{"xml":"C:\\result\\timeline.xml","preview":null}}""");
Require(artifacts?.Outputs?["xml"] is JsonElement xml &&
        xml.GetString() == @"C:\result\timeline.xml", "artifact path");
var state = new UiState("one.mp4", "two.mp4", "out", "25", "balanced", true);
var stateRoundTrip = JsonSerializer.Deserialize<UiState>(JsonSerializer.Serialize(state));
Require(stateRoundTrip == state, "UI state round trip");
Console.WriteLine("PodEdit desktop JSON contract checks: PASS");

static void Require(bool condition, string name)
{
    if (!condition) throw new InvalidOperationException($"Contract check failed: {name}");
}
