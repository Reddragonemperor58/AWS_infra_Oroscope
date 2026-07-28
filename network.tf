# Variables
variable "project_name" {
  type        = string
  description = "The name of the project (e.g., oroscope)"
  default     = "oroscope"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the VPC"
  default     = "10.0.0.0/16"
}

# VPC
resource "aws_vpc" "main" {
  cidr_block = var.vpc_cidr
  enable_dns_support = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

# PRIVATE SUBNET A
resource "aws_subnet" "private_a" {
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.1.0/24"
  availability_zone = "ap-south-2a"

  tags = {
    Name = "${var.project_name}-private-subnet-a"
  }
}

# PRIVATE SUBNET B
resource "aws_subnet" "private_b" {
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.2.0/24"
  availability_zone = "ap-south-2b"


  tags = {
    Name = "${var.project_name}-private-subnet-b"
  }
}

# Attaching the database to the subnet a and b
resource "aws_db_subnet_group" "db_subnet_group" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]

  tags = {
    Name = "${var.project_name}-db-subnet-group"
  }
}

# Attaching security group to database
resource "aws_security_group" "db_sg" {
  name        = "${var.project_name}-db-sg"
  description = "Database security group - no ingress rules yet, adding once Data API connectivity is confirmed in Stage 3"  
  vpc_id      = aws_vpc.main.id
  tags = {
    Name = "${var.project_name}-db-sg"
  }
}

