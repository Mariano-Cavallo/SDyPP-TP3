# outputs.tf

output "worker_ips" {
  description = "IPs públicas de los workers"
  value       = [for vm in google_compute_instance.sobel_worker : vm.network_interface[0].access_config[0].nat_ip]
}

output "worker_names" {
  description = "Nombres de las VMs creadas"
  value       = [for vm in google_compute_instance.sobel_worker : vm.name]
}

output "worker_count" {
  description = "Total de workers desplegados"
  value       = length(google_compute_instance.sobel_worker)
}

output "docker_image" {
  description = "Imagen Docker desplegada en los workers"
  value       = var.docker_image
}

output "worker_ssh_commands" {
  description = "Comandos gcloud para conectarse por SSH a cada worker"
  value = [
    for vm in google_compute_instance.sobel_worker :
    "gcloud compute ssh ${vm.name} --zone=${var.zone} --project=${var.project_id}"
  ]
}

output "worker_log_commands" {
  description = "Comandos para ver el log del bootstrap en cada worker"
  value = [
    for vm in google_compute_instance.sobel_worker :
    "gcloud compute ssh ${vm.name} --zone=${var.zone} --project=${var.project_id} --command='sudo tail -f /var/log/sobel.log'"
  ]
}

output "rabbitmq_internal_ip" {
  description = "IP interna de la VM RabbitMQ"
  value       = google_compute_instance.rabbitmq.network_interface[0].network_ip
}

output "rabbitmq_management_url" {
  description = "URL del panel de administración de RabbitMQ"
  value       = "http://${google_compute_instance.rabbitmq.network_interface[0].access_config[0].nat_ip}:15672"
}