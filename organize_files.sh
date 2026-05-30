#!/bin/bash
# Organizador de Archivos URA
# Organiza los 454 archivos de core/ en estructura lógica por categorías

SOURCE_DIR="/Users/ramonesnaola/URA/ura_ia_1972/core"
TARGET_DIR="/Users/ramonesnaola/URA/ura_ia_1972/core_organized"

# Crear estructura de directorios
mkdir -p "$TARGET_DIR"/{kubernetes,aws,azure,gcp,database,cache,messaging,search,tracing,metrics,logging,monitoring,security,api,web_servers,load_balancer,cdn,storage,serverless,iac,cicd,devops,automation,analytics,integration,resilience,service_mesh,service_discovery,secret_management}

echo "Estructura de directorios creada en $TARGET_DIR"

# Mover archivos por categoría
# Kubernetes
mv "$SOURCE_DIR"/kubernetes_*.py "$TARGET_DIR"/kubernetes/ 2>/dev/null

# AWS
mv "$SOURCE_DIR"/aws_*.py "$SOURCE_DIR"/elastic_load_balancer.py "$SOURCE_DIR"/route53.py "$SOURCE_DIR"/cloudfront.py "$SOURCE_DIR"/cloudwatch.py "$SOURCE_DIR"/s3_*.py "$SOURCE_DIR"/glacier.py "$SOURCE_DIR"/efs.py "$TARGET_DIR"/aws/ 2>/dev/null

# Azure
mv "$SOURCE_DIR"/azure_*.py "$TARGET_DIR"/azure/ 2>/dev/null

# GCP
mv "$SOURCE_DIR"/google_*.py "$SOURCE_DIR"/bigquery.py "$SOURCE_DIR"/cloud_firestore.py "$TARGET_DIR"/gcp/ 2>/dev/null

# Database
mv "$SOURCE_DIR"/postgresql_*.py "$SOURCE_DIR"/mongodb_*.py "$SOURCE_DIR"/cassandra.py "$TARGET_DIR"/database/ 2>/dev/null

# Cache
mv "$SOURCE_DIR"/redis_*.py "$SOURCE_DIR"/memcached_*.py "$TARGET_DIR"/cache/ 2>/dev/null

# Messaging
mv "$SOURCE_DIR"/kafka.py "$SOURCE_DIR"/rabbitmq.py "$SOURCE_DIR"/sqs.py "$TARGET_DIR"/messaging/ 2>/dev/null

# Search
mv "$SOURCE_DIR"/elasticsearch.py "$SOURCE_DIR"/solr.py "$SOURCE_DIR"/opensearch.py "$TARGET_DIR"/search/ 2>/dev/null

# Tracing
mv "$SOURCE_DIR"/jaeger.py "$SOURCE_DIR"/zipkin.py "$SOURCE_DIR"/opentelemetry.py "$TARGET_DIR"/tracing/ 2>/dev/null

# Metrics
mv "$SOURCE_DIR"/prometheus_*.py "$SOURCE_DIR"/grafana_*.py "$SOURCE_DIR"/thanos.py "$TARGET_DIR"/metrics/ 2>/dev/null

# Logging
mv "$SOURCE_DIR"/logstash.py "$SOURCE_DIR"/fluentd.py "$TARGET_DIR"/logging/ 2>/dev/null

# Security
mv "$SOURCE_DIR"/vault.py "$TARGET_DIR"/secret_management/ 2>/dev/null

# Service Mesh
mv "$SOURCE_DIR"/istio_*.py "$SOURCE_DIR"/knative.py "$SOURCE_DIR"/kong_gateway.py "$SOURCE_DIR"/linkerd.py "$TARGET_DIR"/service_mesh/ 2>/dev/null

# Service Discovery
mv "$SOURCE_DIR"/consul_*.py "$SOURCE_DIR"/etcd_*.py "$TARGET_DIR"/service_discovery/ 2>/dev/null

# Web Servers
mv "$SOURCE_DIR"/nginx.py "$SOURCE_DIR"/apache.py "$TARGET_DIR"/web_servers/ 2>/dev/null

# Load Balancer
mv "$SOURCE_DIR"/haproxy.py "$TARGET_DIR"/load_balancer/ 2>/dev/null

# CDN
mv "$SOURCE_DIR"/traefik.py "$SOURCE_DIR"/caddy.py "$SOURCE_DIR"/akamai.py "$TARGET_DIR"/cdn/ 2>/dev/null

# Serverless
mv "$SOURCE_DIR"/aws_lambda.py "$SOURCE_DIR"/azure_functions.py "$SOURCE_DIR"/google_cloud_functions.py "$TARGET_DIR"/serverless/ 2>/dev/null

# IaC
mv "$SOURCE_DIR"/nomad.py "$SOURCE_DIR"/terraform_*.py "$TARGET_DIR"/iac/ 2>/dev/null

# CI/CD
mv "$SOURCE_DIR"/jenkins.py "$SOURCE_DIR"/gitlab_ci.py "$SOURCE_DIR"/github_actions.py "$SOURCE_DIR"/circleci.py "$SOURCE_DIR"/travisci.py "$SOURCE_DIR"/teamcity.py "$TARGET_DIR"/cicd/ 2>/dev/null

# DevOps
mv "$SOURCE_DIR"/ansible.py "$SOURCE_DIR"/chef.py "$SOURCE_DIR"/puppet.py "$SOURCE_DIR"/saltstack.py "$TARGET_DIR"/devops/ 2>/dev/null

echo "Archivos organizados por categorías"
echo "Total de archivos organizados: $(find $TARGET_DIR -name '*.py' | wc -l)"
