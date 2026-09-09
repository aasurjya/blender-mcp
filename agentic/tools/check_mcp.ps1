# Report the state of the Blender MCP setup: Blender processes, the 9876 listener, the bridge, open file.
param([int]$Port = 9876)
Write-Host "--- Blender processes ---"
Get-Process blender, blender-mcp -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, StartTime | Format-Table -AutoSize
Write-Host "--- Listener on $Port ---"
$l = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($l) { $l | Select-Object LocalAddress, LocalPort, OwningProcess | Format-Table -AutoSize } else { Write-Host "NOT LISTENING - start the server in Blender (N-panel > BlenderMCP > Connect to Claude)" -ForegroundColor Yellow }
$count = @($l).Count
if ($count -gt 1) { Write-Host "WARNING: $count listeners on $Port - more than one Blender instance. Close the duplicates." -ForegroundColor Red }
Write-Host "--- Open file (via socket) ---"
$py = Join-Path $PSScriptRoot "blender_socket.py"
if (Test-Path $py) { python $py "import bpy, os; print(os.getpid(), bpy.data.filepath, len(bpy.data.objects), 'objects', 'dirty' if bpy.data.is_dirty else 'clean')" }
