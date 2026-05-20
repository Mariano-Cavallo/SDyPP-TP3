# variables.tf

variable "project_id" {
  description = "ID del proyecto GCP"
  type        = string
}

variable "region" {
  description = "Región GCP"
  type        = string
  default     = "us-central1"
}

variable "cluster_name" {
  description = "Nombre del cluster GKE"
  type        = string
  default     = "sdypp-cluster"
}
