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

variable "master_username_db" {
  type        = string
  description = "Username for the postgresql Aurora db cluster"
  default     = "krishnavamsi"
}

variable "database_name" { 
  type        = string
  description = "Name of the Aurora database"
  default     = "oroscope_aurora"  
}

variable "environment" {
  type        = string
  description = "Deployment environment (dev, staging, prod)"
  default     = "dev"
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}