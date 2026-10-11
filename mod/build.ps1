# Builds mod\bin\SkylinesAgentBridge.dll. With -Install, also copies it into the
# game's Mods folder, keeping the DLL it replaces as SkylinesAgentBridge.dll.bak.
# Install only while the game is closed.
param(
    [string]$Game = "D:\Steam\steamapps\common\Cities_Skylines",
    [switch]$Install
)

$ErrorActionPreference = "Stop"

$managed = Join-Path $Game "Cities_Data\Managed"
$csc = "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if (!(Test-Path $csc)) { throw "csc.exe was not found at $csc" }
if (!(Test-Path (Join-Path $managed "ICities.dll"))) { throw "Game DLLs were not found at $managed" }

$out = Join-Path $PSScriptRoot "bin"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$target = Join-Path $out "SkylinesAgentBridge.dll"

# /nostdlib with the game's own mscorlib: the game runs Mono 2.x, and a DLL that
# points at .NET 4's core library may not load there.
$refs = "mscorlib", "System", "System.Core", "ICities", "Assembly-CSharp", "Assembly-CSharp-firstpass", "ColossalManaged", "UnityEngine" |
    ForEach-Object { "/reference:$managed\$_.dll" }
$sources = Get-ChildItem (Join-Path $PSScriptRoot "src") -Filter *.cs | Sort-Object Name | ForEach-Object FullName

& $csc /nologo /nostdlib /noconfig /target:library /optimize+ /warnaserror+ /out:$target @refs $sources
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Built $target"

if ($Install) {
    if (Get-Process Cities -ErrorAction SilentlyContinue) { throw "Close Cities: Skylines before installing." }
    $modDir = Join-Path $env:LOCALAPPDATA "Colossal Order\Cities_Skylines\Addons\Mods\SkylinesAgentBridge"
    New-Item -ItemType Directory -Force -Path $modDir | Out-Null
    $installed = Join-Path $modDir "SkylinesAgentBridge.dll"
    $backup = "$installed.bak"
    if ((Test-Path $installed) -and !(Test-Path $backup)) { Copy-Item $installed $backup }
    Copy-Item $target $installed -Force
    Write-Host "Installed to $modDir"
}
