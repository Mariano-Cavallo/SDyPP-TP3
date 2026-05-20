# outputs.tf

output "cluster_name" {
  description = "Nombre del cluster GKE"
  value       = google_container_cluster.primary.name
}

output "cluster_endpoint" {
  description = "Endpoint del API server de Kubernetes"
  value       = google_container_cluster.primary.endpoint
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "Certificado CA del cluster"
  value       = google_container_cluster.primary.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "configure_kubectl" {
  description = "Comando para configurar kubectl localmente"
  value       = "gcloud container clusters get-credentials ${var.cluster_name} --region ${var.region} --project ${var.project_id}"
}

output "node_pools" {
  description = "Node pools creados"
  value = {
    infra = google_container_node_pool.infra.name
    app   = google_container_node_pool.app.name
  }
}
