# Points the game camera at a spot and saves a screenshot of the game window.
# Use: screenshot.ps1 -X -1187 -Z 90 -Size 260 -Out shot.png
param(
    [Parameter(Mandatory)] [double]$X,
    [Parameter(Mandatory)] [double]$Z,
    [double]$Size = 300,
    [Parameter(Mandatory)] [string]$Out,
    [string]$Bridge = "http://127.0.0.1:32123"
)

$ErrorActionPreference = "Stop"
$body = @{ position = @{ x = $X; z = $Z }; size = $Size } | ConvertTo-Json -Compress
Invoke-WebRequest "$Bridge/commands/set-camera" -Method Post -Body $body -ContentType "application/json" -UseBasicParsing | Out-Null

Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class GameWindow {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    public struct RECT { public int L, T, R, B; }
}
'@

$game = Get-Process Cities
[GameWindow]::ShowWindow($game.MainWindowHandle, 9) | Out-Null
[GameWindow]::SetForegroundWindow($game.MainWindowHandle) | Out-Null
Start-Sleep -Seconds 3   # let the camera settle and the window come to the front

$r = New-Object GameWindow+RECT
[GameWindow]::GetWindowRect($game.MainWindowHandle, [ref]$r) | Out-Null
$bitmap = New-Object System.Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T)
[System.Drawing.Graphics]::FromImage($bitmap).CopyFromScreen($r.L, $r.T, 0, 0, $bitmap.Size)
$half = New-Object System.Drawing.Bitmap $bitmap, ([int]($bitmap.Width / 2)), ([int]($bitmap.Height / 2))
$half.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "Saved $Out"
