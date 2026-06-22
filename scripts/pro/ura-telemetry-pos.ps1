<#
.SYNOPSIS
    URA POS Telemetry Agent — Envía métricas del sistema al Master GX10.
.DESCRIPTION
    Script PowerShell para caja0 (Windows). Ejecuta push asíncrono cada 30s
    de CPU, RAM, estado del terminal de venta hacia ura-audit-api (puerto 8002).
    
    Instalación como tarea programada:
      powershell -ExecutionPolicy Bypass -File C:\URA\scripts\ura-telemetry.ps1

    O como Scheduled Task (recomendado):
      Trigger: cada 1 minuto, reinicio
      Acción: powershell.exe -ExecutionPolicy Bypass -File "C:\URA\scripts\ura-telemetry.ps1" -ScheduledRun
.NOTES
    Node:    caja0 (100.127.217.113)
    Target:  GX10 Tailscale (100.72.103.12:8002)
    Fecha:   2026-06-20
#>

param(
    [switch]$ScheduledRun
)

# Configuración
$MasterUrl = "http://gx10-64c3-1.tail7b3cf3.ts.net:8002/api/v1/telemetry"
$Headers = @{
    "Authorization" = "Bearer URA_SECRET_NODE_TOKEN_HASH_XYZ"
    "Content-Type"  = "application/json"
}
$IntervalSeconds = 30
$MaxRetries = 3

function Send-Telemetry {
    try {
        $Cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
        $Os = Get-CimInstance Win32_OperatingSystem
        $RamFree = [math]::Round($Os.FreePhysicalMemory / 1KB, 2)
        $RamTotal = [math]::Round($Os.TotalVisibleMemorySize / 1KB, 2)
        $Disk = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | 
            Select-Object DeviceID, @{N='FreeGB';E={[math]::Round($_.FreeSpace/1GB,2)}},
                                    @{N='TotalGB';E={[math]::Round($_.Size/1GB,2)}}

        $Payload = @{
            node_id        = $env:COMPUTERNAME
            os             = "Windows"
            timestamp      = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
            status         = "deterministic_ok"
            cpu_usage_pct  = [math]::Round($Cpu, 1)
            ram_free_mb    = $RamFree
            ram_total_mb   = $RamTotal
            ram_used_pct   = [math]::Round(($RamTotal - $RamFree) / $RamTotal * 100, 1)
            disks          = ($Disk | ForEach-Object { "$($_.DeviceID) $($_.FreeGB)GB/$($_.TotalGB)GB" }) -join "; "
        } | ConvertTo-Json -Compress

        for ($i = 0; $i -lt $MaxRetries; $i++) {
            try {
                Invoke-RestMethod -Uri $MasterUrl -Method Post -Body $Payload `
                    -Headers $Headers -TimeoutSec 5
                return $true
            } catch {
                if ($i -eq $MaxRetries - 1) { throw }
                Start-Sleep -Seconds 2
            }
        }
    } catch {
        # Fallo silencioso — no interrumpir el terminal de venta
        if (-not $ScheduledRun) {
            Write-Warning "Telemetry push failed: $_"
        }
    }
    return $false
}

# Modo Scheduled Task: un solo envío y salida
if ($ScheduledRun) {
    Send-Telemetry | Out-Null
    exit 0
}

# Modo interactivo: loop perpetuo
Write-Host "URA POS Telemetry Agent para caja0"
Write-Host "Enviando a $MasterUrl cada ${IntervalSeconds}s"
Write-Host "Presione Ctrl+C para detener"
Write-Host ""

while ($true) {
    if (Send-Telemetry) {
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] OK" -ForegroundColor Green
    } else {
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] FAIL" -ForegroundColor Red
    }
    Start-Sleep -Seconds $IntervalSeconds
}
