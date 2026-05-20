# variables.tf

# ─── PROYECTO GCP ──────────────────────────────────────────────

variable "project_id" {
  description = "ID del proyecto en GCP"
  type        = string
  validation {
    condition     = length(var.project_id) > 0
    error_message = "project_id no puede estar vacío."
  }
}

variable "region" {
  description = "Región donde se crean los recursos"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "Zona dentro de la región"
  type        = string
  default     = "us-central1-a"
}

# ─── WORKERS ───────────────────────────────────────────────────

variable "worker_count" {
  description = "Cantidad de VMs worker a crear"
  type        = number
  default     = 2
  validation {
    condition     = var.worker_count >= 1 && var.worker_count <= 20
    error_message = "worker_count debe estar entre 1 y 20."
  }
}

variable "machine_type" {
  description = "Tipo de máquina GCP para los workers"
  type        = string
  default     = "e2-medium"
}

variable "ssh_allowed_cidrs" {
  description = "CIDRs que pueden conectarse por SSH a los workers (ej: tu IP pública)"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# ─── APLICACIÓN ────────────────────────────────────────────────

variable "docker_image" {
  description = "Imagen Docker en Docker Hub con el script Sobel"
  type        = string
  default     = "marianocavallo/sobel-worker:latest"
}

