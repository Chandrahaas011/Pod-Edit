using System.Windows;

namespace PodEdit.Desktop;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        var window = new MainWindow();
        if (e.Args.Contains("--smoke-test", StringComparer.OrdinalIgnoreCase)) {
            window.Measure(new Size(1040, 720));
            window.Arrange(new Rect(0, 0, 1040, 720));
            Shutdown(0);
            return;
        }
        MainWindow = window;
        window.Show();
    }
}
