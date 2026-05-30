# URA Infrastructure as Code - Terraform

provider "aws" {
  region = var.aws_region
}

provider "kubernetes" {
  config_path = var.kubeconfig_path
}

# VPC
resource "aws_vpc" "ura_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = {
    Name = "ura-vpc"
    Environment = var.environment
  }
}

# Subnets
resource "aws_subnet" "public_subnet" {
  count                   = 2
  vpc_id                  = aws_vpc.ura_vpc.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  
  tags = {
    Name = "ura-public-subnet-${count.index}"
    Environment = var.environment
  }
}

resource "aws_subnet" "private_subnet" {
  count             = 2
  vpc_id            = aws_vpc.ura_vpc.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 2)
  availability_zone = data.aws_availability_zones.available.names[count.index]
  
  tags = {
    Name = "ura-private-subnet-${count.index}"
    Environment = var.environment
  }
}

# EKS Cluster
resource "aws_eks_cluster" "ura_cluster" {
  name     = var.cluster_name
  role_arn = aws_iam_role.eks_role.arn
  version = var.kubernetes_version
  
  vpc_config {
    subnet_ids = concat(
      aws_subnet.public_subnet[*].id,
      aws_subnet.private_subnet[*].id
    )
  }
  
  depends_on = [
    aws_iam_role_policy_attachment.eks_policy
  ]
  
  tags = {
    Environment = var.environment
  }
}

# IAM Role for EKS
resource "aws_iam_role" "eks_role" {
  name = "${var.cluster_name}-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "eks_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_role.name
}

# RDS PostgreSQL
resource "aws_db_instance" "ura_db" {
  identifier     = var.db_identifier
  engine         = "postgres"
  engine_version = "14.7"
  instance_class = var.db_instance_class
  allocated_storage = var.db_storage
  db_name        = var.db_name
  username       = var.db_username
  password       = var.db_password
  
  vpc_security_group_ids = [aws_security_group.db_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.ura_db_subnet.name
  
  backup_retention_period = 7
  skip_final_snapshot    = false
  
  tags = {
    Environment = var.environment
  }
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "ura_redis" {
  cluster_id           = var.redis_cluster_id
  engine               = "redis"
  node_type            = var.redis_node_type
  num_cache_nodes      = var.redis_num_nodes
  parameter_group_name = "default.redis7"
  engine_version       = "7.0"
  port                 = 6379
  
  subnet_group_name  = aws_elasticache_subnet_group.ura_redis_subnet.name
  security_group_ids = [aws_security_group.redis_sg.id]
  
  tags = {
    Environment = var.environment
  }
}

# Variables
variable "aws_region" {
  default = "eu-west-1"
}

variable "environment" {
  default = "production"
}

variable "vpc_cidr" {
  default = "10.0.0.0/16"
}

variable "cluster_name" {
  default = "ura-cluster"
}

variable "kubernetes_version" {
  default = "1.28"
}

variable "db_instance_class" {
  default = "db.t3.medium"
}

variable "db_storage" {
  default = 100
}
