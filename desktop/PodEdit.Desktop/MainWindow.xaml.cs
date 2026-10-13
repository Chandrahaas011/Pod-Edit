using Microsoft.Win32;
using System.Diagnostics;
using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;

namespace PodEdit.Desktop;

public partial class MainWindow : Window
{
    private Process? _worker;
    private string? _cancelFile;
    private string? _timelinePath;
    private string? _previewPath;
    private bool _lightTheme;
    private bool _closeAfterWorker;
    private readonly Stopwatch _elapsed = new();
    private readonly DispatcherTimer _timer = new() { Interval = TimeSpan.FromSeconds(1) };

    public MainWindow()
    {
        InitializeComponent();
        AllowDrop = true;
        DragOver += Window_DragOver;
        Drop += Window_Drop;
        _timer.Tick += (_, _) => UpdateTiming();
        if (FindProjectRoot() is { } root && UiStateStore.Load(root) is { } state) {
            Camera1Box.Text = state.Camera1;
            Camera2Box.Text = state.Camera2;
            OutputBox.Text = state.Output;
            MinutesBox.Text = state.Minutes;
            PreviewCheckBox.IsChecked = state.RenderPreview;
            foreach (ComboBoxItem item in ProfileBox.Items)
                if (string.Equals(item.Content?.ToString(), state.EditorialProfile,
                                  StringComparison.OrdinalIgnoreCase))
                    ProfileBox.SelectedItem = item;
            StatusText.Text = "Previous job settings restored";
        }
    }

    private static readonly HashSet<string> VideoExtensions = new(StringComparer.OrdinalIgnoreCase) {
        ".mp4", ".mov", ".mkv", ".avi", ".mxf"
    };

    private static string? PickVideo()
    {
        var dialog = new OpenFileDialog {
            Filter = "Video files|*.mp4;*.mov;*.mkv;*.avi;*.mxf|All files|*.*",
            CheckFileExists = true
        };
        return dialog.ShowDialog() == true ? dialog.FileName : null;
    }

    private void BrowseCamera1_Click(object sender, RoutedEventArgs e) =>
        Camera1Box.Text = PickVideo() ?? Camera1Box.Text;

    private void BrowseCamera2_Click(object sender, RoutedEventArgs e) =>
        Camera2Box.Text = PickVideo() ?? Camera2Box.Text;

    private void BrowseOutput_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFolderDialog { Multiselect = false, Title = "Choose PodEdit output folder" };
        if (dialog.ShowDialog() == true) OutputBox.Text = dialog.FolderName;
    }

    private void SwapCameras_Click(object sender, RoutedEventArgs e) =>
        (Camera1Box.Text, Camera2Box.Text) = (Camera2Box.Text, Camera1Box.Text);

    private void Window_DragOver(object sender, DragEventArgs e)
    {
        e.Effects = e.Data.GetDataPresent(DataFormats.FileDrop)
            ? DragDropEffects.Copy : DragDropEffects.None;
        e.Handled = true;
    }

    private void Window_Drop(object sender, DragEventArgs e)
    {
        if (e.Data.GetData(DataFormats.FileDrop) is not string[] files) return;
        var videos = files.Where(path => File.Exists(path) && VideoExtensions.Contains(Path.GetExtension(path)))
                          .Take(2).ToArray();
        if (videos.Length > 0) Camera1Box.Text = videos[0];
        if (videos.Length > 1) Camera2Box.Text = videos[1];
        StatusText.Text = videos.Length == 2 ? "Two cameras ready" : "Drop one more camera file";
    }

    private async void Preflight_Click(object sender, RoutedEventArgs e) => await RunAsync(preflightOnly: true);
    private async void Start_Click(object sender, RoutedEventArgs e) => await RunAsync(preflightOnly: false);

    private void OpenOutput_Click(object sender, RoutedEventArgs e)
    {
        if (!Directory.Exists(OutputBox.Text)) return;
        Process.Start(new ProcessStartInfo("explorer.exe", $"\"{Path.GetFullPath(OutputBox.Text)}\"") {
            UseShellExecute = true
        });
    }

    private void ShowTimeline_Click(object sender, RoutedEventArgs e) => ShowInExplorer(_timelinePath);
    private void PlayPreview_Click(object sender, RoutedEventArgs e) => OpenFile(_previewPath);

    private void Theme_Click(object sender, RoutedEventArgs e)
    {
        _lightTheme = !_lightTheme;
        SetBrush("WindowBrush", _lightTheme ? "#F5F7FA" : "#0D1118");
        SetBrush("ForegroundBrush", _lightTheme ? "#17202A" : "#EDF5FF");
        SetBrush("MutedBrush", _lightTheme ? "#526577" : "#9CB0C7");
        SetBrush("PanelBrush", _lightTheme ? "#E5EBF2" : "#171C26");
        SetBrush("LogBrush", _lightTheme ? "#FFFFFF" : "#0A0E14");
        SetBrush("LogForegroundBrush", _lightTheme ? "#12344D" : "#BFE6FF");
        ThemeButton.Content = _lightTheme ? "Dark theme" : "Light theme";
    }

    private static void SetBrush(string key, string color) =>
        Application.Current.Resources[key] = new System.Windows.Media.SolidColorBrush(
            (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString(color));

    private static void ShowInExplorer(string? path)
    {
        if (path is null || !File.Exists(path)) return;
        Process.Start(new ProcessStartInfo("explorer.exe", $"/select,\"{path}\"") { UseShellExecute = true });
    }

    private static void OpenFile(string? path)
    {
        if (path is null || !File.Exists(path)) return;
        Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
    }

    private void Cancel_Click(object sender, RoutedEventArgs e)
    {
        if (_cancelFile is null) return;
        File.WriteAllText(_cancelFile, "cancel\n");
        StatusText.Text = "Cancelling at the next safe boundary…";
        CancelButton.IsEnabled = false;
    }

    protected override void OnClosing(CancelEventArgs e)
    {
        if (_worker is not null) {
            e.Cancel = true;
            _closeAfterWorker = true;
            if (_cancelFile is not null && !File.Exists(_cancelFile))
                File.WriteAllText(_cancelFile, "cancel\n");
            StatusText.Text = "Cancelling safely before closing…";
            StartButton.IsEnabled = false;
            PreflightButton.IsEnabled = false;
            CancelButton.IsEnabled = false;
            return;
        }
        base.OnClosing(e);
    }

    private static DirectoryInfo? FindProjectRoot()
    {
        var current = new DirectoryInfo(AppContext.BaseDirectory);
        while (current is not null) {
            if (File.Exists(Path.Combine(current.FullName, "worker.py")) ||
                File.Exists(Path.Combine(current.FullName, "PodEdit.Worker.exe"))) return current;
            current = current.Parent;
        }
        return null;
    }

    private bool TryCreateJob(out WorkerJob? job, out string error)
    {
        job = null;
        error = "";
        if (!File.Exists(Camera1Box.Text) || !File.Exists(Camera2Box.Text)) {
            error = "Choose two existing camera files."; return false;
        }
        if (StringComparer.OrdinalIgnoreCase.Equals(
                Path.GetFullPath(Camera1Box.Text), Path.GetFullPath(Camera2Box.Text))) {
            error = "Camera 1 and Camera 2 must be different files."; return false;
        }
        if (string.IsNullOrWhiteSpace(OutputBox.Text)) {
            error = "Choose an output folder."; return false;
        }
        if (!double.TryParse(MinutesBox.Text, NumberStyles.Float, CultureInfo.InvariantCulture,
                             out var minutes) || minutes <= 0) {
            error = "Minutes must be a positive number."; return false;
        }
        var profile = ((ComboBoxItem)ProfileBox.SelectedItem).Content.ToString() ?? "balanced";
        job = new WorkerJob(1, Guid.NewGuid().ToString(), Path.GetFullPath(Camera1Box.Text),
            Path.GetFullPath(Camera2Box.Text), Path.GetFullPath(OutputBox.Text),
            new JobOptions(minutes * 60, profile, Offline: true,
                           NoPreview: PreviewCheckBox.IsChecked != true));
        return true;
    }

    private async Task RunAsync(bool preflightOnly)
    {
        if (_worker is not null) return;
        if (!TryCreateJob(out var job, out var error)) {
            MessageBox.Show(this, error, "PodEdit", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }
        var root = FindProjectRoot();
        if (root is null) {
            MessageBox.Show(this, "Could not locate the PodEdit worker.", "PodEdit",
                            MessageBoxButton.OK, MessageBoxImage.Error); return;
        }
        var packagedWorker = Path.Combine(root.FullName, "PodEdit.Worker.exe");
        var python = Path.Combine(root.FullName, ".venv", "Scripts", "python.exe");
        var packaged = File.Exists(packagedWorker);
        if (!packaged && !File.Exists(python)) {
            MessageBox.Show(this, "The PodEdit worker runtime is missing.", "PodEdit",
                            MessageBoxButton.OK, MessageBoxImage.Error); return;
        }

        UiStateStore.Save(root, new UiState(
            Camera1Box.Text, Camera2Box.Text, OutputBox.Text, MinutesBox.Text,
            ((ComboBoxItem)ProfileBox.SelectedItem).Content.ToString() ?? "balanced",
            PreviewCheckBox.IsChecked == true));

        Directory.CreateDirectory(job!.Output);
        var control = Path.Combine(job.Output, ".podedit-control");
        Directory.CreateDirectory(control);
        var jobFile = Path.Combine(control, $"{job.JobId}.job.json");
        var eventsFile = Path.Combine(control, $"{job.JobId}.events.jsonl");
        _cancelFile = Path.Combine(control, $"{job.JobId}.cancel");
        File.WriteAllText(jobFile, JsonSerializer.Serialize(job, new JsonSerializerOptions { WriteIndented = true }));
        if (File.Exists(_cancelFile)) File.Delete(_cancelFile);

        var arguments = packaged
            ? $"--job \"{jobFile}\" --events \"{eventsFile}\""
            : $"worker.py --job \"{jobFile}\" --events \"{eventsFile}\"";
        if (preflightOnly) arguments += " --preflight";
        else arguments += $" --cancel-file \"{_cancelFile}\"";
        var start = new ProcessStartInfo(packaged ? packagedWorker : python, arguments) {
            WorkingDirectory = root.FullName, UseShellExecute = false,
            CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true
        };

        SetRunning(true, preflightOnly ? "Checking setup…" : "Starting worker…");
        _elapsed.Restart();
        _timer.Start();
        OpenOutputButton.IsEnabled = false;
        ShowTimelineButton.IsEnabled = false;
        PlayPreviewButton.IsEnabled = false;
        _timelinePath = null;
        _previewPath = null;
        LogBox.Clear();
        try {
            _worker = Process.Start(start) ?? throw new InvalidOperationException("Worker did not start.");
            CancelButton.IsEnabled = !preflightOnly;
            var stdout = PumpTextAsync(_worker.StandardOutput);
            var stderr = PumpTextAsync(_worker.StandardError);
            var events = PumpEventsAsync(eventsFile, _worker);
            await _worker.WaitForExitAsync();
            await Task.WhenAll(stdout, stderr, events);
            StatusText.Text = _worker.ExitCode switch {
                0 when preflightOnly => "Setup check passed",
                0 => "Edit completed",
                130 => "Cancelled — completed checkpoints are reusable",
                2 => "Setup check failed",
                _ => $"Worker failed (exit {_worker.ExitCode})"
            };
            OpenOutputButton.IsEnabled = _worker.ExitCode == 0 && !preflightOnly;
        }
        catch (Exception ex) {
            StatusText.Text = "Worker could not run";
            LogBox.AppendText(ex + Environment.NewLine);
        }
        finally {
            _timer.Stop();
            _elapsed.Stop();
            UpdateTiming();
            _worker?.Dispose(); _worker = null;
            SetRunning(false, StatusText.Text);
            if (_closeAfterWorker) {
                _closeAfterWorker = false;
                _ = Dispatcher.BeginInvoke(Close);
            }
        }
    }

    private async Task PumpTextAsync(StreamReader reader)
    {
        while (await reader.ReadLineAsync() is { } line) {
            await Dispatcher.InvokeAsync(() => {
                LogBox.AppendText(line + Environment.NewLine); LogBox.ScrollToEnd();
            });
        }
    }

    private async Task PumpEventsAsync(string path, Process process)
    {
        long byteOffset = 0;
        var pending = "";

        async Task DrainAsync()
        {
            if (!File.Exists(path)) return;
            try {
                await using var stream = new FileStream(
                    path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete,
                    bufferSize: 4096, useAsync: true);
                if (stream.Length < byteOffset) { byteOffset = 0; pending = ""; }
                stream.Seek(byteOffset, SeekOrigin.Begin);
                using var reader = new StreamReader(stream, System.Text.Encoding.UTF8,
                    detectEncodingFromByteOrderMarks: true, bufferSize: 4096, leaveOpen: true);
                var appended = await reader.ReadToEndAsync();
                byteOffset = stream.Position;
                if (appended.Length == 0) return;

                var text = pending + appended;
                var lines = text.Split('\n');
                pending = lines[^1];
                foreach (var rawLine in lines[..^1]) {
                    var line = rawLine.TrimEnd('\r');
                    if (line.Length == 0) continue;
                    WorkerEvent? item = null;
                    try { item = JsonSerializer.Deserialize<WorkerEvent>(line); }
                    catch (JsonException) { }
                    if (item is not null)
                        await Dispatcher.InvokeAsync(() => ApplyEvent(item));
                }
            }
            catch (IOException) { }
        }

        while (!process.HasExited) {
            await DrainAsync();
            await Task.Delay(200);
        }
        // The worker can append its artifact/completion events immediately
        // before exit. One delayed final drain closes that race.
        await Task.Delay(100);
        await DrainAsync();
        if (!string.IsNullOrWhiteSpace(pending)) {
            try {
                var item = JsonSerializer.Deserialize<WorkerEvent>(pending.TrimEnd('\r'));
                if (item is not null)
                    await Dispatcher.InvokeAsync(() => ApplyEvent(item));
            }
            catch (JsonException) { }
        }
    }

    private void ApplyEvent(WorkerEvent item)
    {
        if (item.Progress is { } progress) Progress.Value = Math.Clamp(progress, 0, 1);
        if (item.Type == "stage_started") StatusText.Text = item.Name ?? "Processing…";
        if (item.Type is "job_rejected" or "job_warning")
            LogBox.AppendText($"[{item.Code}] {item.Message}{Environment.NewLine}");
        if (item.Type == "source_inspected" && item.Camera is { } camera) {
            var summary = $"{item.Width}×{item.Height} · {item.Fps:0.###} fps · " +
                          $"{item.DurationSeconds / 60:0.0} min";
            if (camera == 1) Camera1Info.Text = summary;
            if (camera == 2) Camera2Info.Text = summary;
        }
        if (item.Type == "artifacts_available") {
            Progress.Value = 1;
            _timelinePath = ArtifactPath(item, "xml");
            _previewPath = ArtifactPath(item, "preview");
            ShowTimelineButton.IsEnabled = File.Exists(_timelinePath);
            PlayPreviewButton.IsEnabled = File.Exists(_previewPath);
        }
    }

    private void UpdateTiming()
    {
        var elapsed = _elapsed.Elapsed;
        var elapsedText = $"Elapsed {elapsed:hh\\:mm\\:ss}";
        if (_elapsed.IsRunning && Progress.Value is > 0.02 and < 1) {
            var totalSeconds = elapsed.TotalSeconds / Progress.Value;
            var remaining = TimeSpan.FromSeconds(Math.Max(0, totalSeconds - elapsed.TotalSeconds));
            TimingText.Text = $"{elapsedText} · ETA {remaining:hh\\:mm\\:ss}";
        } else {
            TimingText.Text = elapsedText;
        }
    }

    private static string? ArtifactPath(WorkerEvent item, string name)
    {
        if (item.Outputs is null || !item.Outputs.TryGetValue(name, out var value)
            || value is not JsonElement element || element.ValueKind != JsonValueKind.String)
            return null;
        return element.GetString();
    }

    private void SetRunning(bool running, string status)
    {
        StatusText.Text = status;
        StartButton.IsEnabled = !running;
        PreflightButton.IsEnabled = !running;
        CancelButton.IsEnabled = running && _worker is not null;
        if (!running && Progress.Value < 1) Progress.Value = 0;
    }
}
