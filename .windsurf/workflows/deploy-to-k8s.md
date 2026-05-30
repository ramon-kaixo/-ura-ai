---
description: Desplegar URA a Kubernetes
---

Despliegue la aplicación URA en el clúster de Kubernetes.

## Prerrequisitos
- kubectl configurado
- Acceso al clúster de Kubernetes

## Pasos

1. Aplicar configuraciones
```bash
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/nginx-lb.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/sonarqube.yaml
kubectl apply -f k8s/minio.yaml
kubectl apply -f k8s/grafana-dashboard.yaml
```

2. Verificar despliegue
```bash
kubectl get pods -n ura
kubectl get services -n ura
```

3. Verificar logs
```bash
kubectl logs -f deployment/ura-app -n ura
```

## Troubleshooting

Si un pod no inicia:
```bash
kubectl describe pod <pod-name> -n ura
kubectl logs <pod-name> -n ura
```

Si un servicio no es accesible:
```bash
kubectl get endpoints <service-name> -n ura
```
