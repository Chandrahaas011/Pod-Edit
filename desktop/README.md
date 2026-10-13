# PodEdit Desktop

This is the Milestone 3 native Windows thin client. It owns presentation and
job control only; all media analysis and editing remain in `worker.py` and the
Python `pipeline/` package.

## Development build

No third-party NuGet package is required. Keep .NET state inside the repository:

```powershell
$projectRoot = (Resolve-Path .).Path
$env:DOTNET_CLI_HOME = "$projectRoot\.dotnet_cli"
$env:NUGET_PACKAGES = "$projectRoot\.nuget\packages"
$env:APPDATA = "$projectRoot\.appdata"
$env:LOCALAPPDATA = "$projectRoot\.localappdata"
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = "1"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"
dotnet build desktop\PodEdit.Desktop\PodEdit.Desktop.csproj --configfile NuGet.Config
dotnet run --project desktop\PodEdit.Desktop.ContractChecks --configfile NuGet.Config
desktop\PodEdit.Desktop\bin\Debug\net9.0-windows\PodEdit.Desktop.exe --smoke-test
```

The development client locates `worker.py` by walking upward from its executable
directory and uses `.venv\Scripts\python.exe`. A packaged release will replace
that development lookup with the frozen worker path from the installation
layout.

## Current UI contract

- choose or drag-and-drop two video sources, swap their roles, and select an output folder;
- select duration and editorial pacing;
- run worker preflight without processing;
- start a job, follow structured stage progress plus cockpit output, and request
  cooperative cancellation;
- tail JSONL events incrementally (constant work per update rather than
  rereading an ever-growing log) and perform a final drain after worker exit;
- show completion, cancellation, setup rejection, or failure distinctly.
- defer window shutdown until an active worker acknowledges cooperative
  cancellation, preventing orphaned neural processes;
- open the completed job's output folder from the results state.
- reveal the generated timeline in Explorer and launch the preview when those
  artifacts are reported by the worker manifest.

Job and event JSON files are kept under the selected output folder's
`.podedit-control` directory. Tokens are never written into the job.
The development client atomically remembers the last non-secret UI selections
in the repository-local ignored `.desktop_state/last-job.json`. A packaged build
will move this state to its per-user application-data directory.
