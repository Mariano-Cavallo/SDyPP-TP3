# provider.tf

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # Mismo bucket GCS que hit2, distinto prefix
  # Reemplazar "TU_BUCKET_TFSTATE" con el nombre real del bucket
  backend "gcs" {
    bucket = "sdpp-tp3-tfstate"
    prefix = "hit3/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
