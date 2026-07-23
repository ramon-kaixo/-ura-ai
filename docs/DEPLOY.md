# URA Deployment Guide

## Local
python -m motor.assistant.main

## Docker
docker-compose up --build

## Production
- Set URA_ENV=production
- Configure secrets via environment variables
- Health endpoint: /health
## systemd
sudo cp ura.service /etc/systemd/system/
sudo systemctl enable --now ura

## Environment Variables
- `URA_ENV` - Set to "production" for production mode
- `URA_HOST` - Listen address (default: 0.0.0.0)
- `URA_PORT` - Listen port (default: 8000)
- `ASUS_HOST` - ASUS server IP (default: 100.72.103.12)
- `ASUS_PORT` - ASUS server port (default: 4198)
Docker build requiere writable filesystem. En GX10 usar: docker build --tmpfs /tmp
Docker build requiere writable filesystem. En entornos RO como GX10 usar: docker build --tmpfs /tmp -t ura .
