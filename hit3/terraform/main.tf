# main.tf

resource "google_container_cluster" "primary" {
  name     = var.cluster_name
  location = var.region

  remove_default_node_pool = true
  initial_node_count       = 1

  networking_mode = "VPC_NATIVE"
  ip_allocation_policy {}

  deletion_protection = false

  # Forzar pd-standard en el pool temporal que GKE crea antes de borrarlo
  node_config {
    machine_type = "e2-medium"
    disk_type    = "pd-standard"
    disk_size_gb = 30
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}

# Pool para infraestructura: RabbitMQ, Prometheus, Grafana
resource "google_container_node_pool" "infra" {
  name       = "infra-pool"
  location   = var.region
  cluster    = google_container_cluster.primary.name
  node_count = 1

  node_config {
    machine_type = "e2-medium"
    disk_type    = "pd-standard"
    disk_size_gb = 30
    labels       = { role = "infra" }
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}

# Pool para aplicaciones: workers, centralizador, dlq-consumer
resource "google_container_node_pool" "app" {
  name       = "app-pool"
  location   = var.region
  cluster    = google_container_cluster.primary.name
  node_count = 1

  node_config {
    machine_type = "e2-medium"
    disk_type    = "pd-standard"
    disk_size_gb = 30
    labels       = { role = "app" }
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}
