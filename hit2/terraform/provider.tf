# provider.tf

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # Configurar con: terraform init -backend-config="bucket=TU_BUCKET"
  # O reemplazar "TU_BUCKET_TFSTATE" por el nombre real del bucket GCS
  backend "gcs" {
    bucket = "TU_BUCKET_TFSTATE"
    prefix = "sobel/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}