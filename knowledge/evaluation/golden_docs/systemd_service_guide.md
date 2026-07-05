# Systemd Service Management for URA

URA uses systemd for service lifecycle management on the GX10.

## Service Files

Service files are located in:
- System services: `/etc/systemd/system/`
- User services: `/etc/systemd/user/`

## Key Configuration

- `Restart=on-failure` with `RestartSec=10` for resilience
- `TimeoutStartSec=180` for models with long cold-boot times
- `CPUQuota=40%` for CPU-bound services
- `MemoryHigh` and `MemoryMax` limits for memory protection

## Timer Services

- `tuneladora.timer`: Runs every 6 hours for continuous improvement pipeline

## Health Checks

Systemd service health is monitored via:
- `systemctl is-active <service>`
- `systemctl show <service> -p MainPID`
- Custom health scripts in scripts/pro/
