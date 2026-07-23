# URA Deployment Guide

## Local
python -m motor.assistant.main

## Docker
docker-compose up --build

## Production
- Set URA_ENV=production
- Configure secrets via environment variables
- Health endpoint: /health
