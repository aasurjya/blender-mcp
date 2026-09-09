# Start Blender 5.1 on a .blend with the BlenderMCP addon enabled and its socket server started.
# Usage:  powershell -File tools\launch_blender.ps1 -Blend "D:\aasurjya\Blender\mcp\projects\sail_tower\blend\sail_tower_work.blend"
# Refuses to start a second instance (two listeners on 9876 corrupt the workflow).
param(
    [Parameter(Mandatory = $true)][string]$Blend,
    [string]$BlenderExe = "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
    [int]$Port = 9876,
    [int]$WaitSeconds = 25
)
$running = Get-Process blender -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "Blender already running (PID $($running.Id -join ', ')). Not starting another. Use check_mcp.ps1." -ForegroundColor Yellow
    exit 2
}
if (-not (Test-Path $Blend)) { Write-Error "Blend file not found: $Blend"; exit 1 }
$expr = "import bpy; bpy.ops.preferences.addon_enable(module=\`"addon\`"); bpy.context.scene.blendermcp_port=$Port; bpy.ops.blendermcp.start_server()"
Start-Process -FilePath $BlenderExe -ArgumentList @("`"$Blend`"", "--python-expr", "`"$expr`"")
Start-Sleep -Seconds $WaitSeconds
$listen = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listen) { Write-Host "OK: Blender PID $($listen.OwningProcess) listening on 127.0.0.1:$Port" -ForegroundColor Green }
else { Write-Host "Blender started but nothing listens on $Port yet - open the BlenderMCP N-panel and click 'Connect to Claude'." -ForegroundColor Yellow; exit 3 }
