# main.tf

# ─── RED ───────────────────────────────────────────────────────
resource "google_compute_network" "sobel_network" {
  name                    = "sobel-network"
  auto_create_subnetworks = true
}

# SSH: solo desde las IPs configuradas en var.ssh_allowed_cidrs
resource "google_compute_firewall" "sobel_firewall_ssh" {
  name    = "sobel-firewall-ssh"
  network = google_compute_network.sobel_network.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = var.ssh_allowed_cidrs
  target_tags   = ["sobel-worker"]
}

# Puerto de app: solo tráfico interno de la red sobel
resource "google_compute_firewall" "sobel_firewall_app" {
  name    = "sobel-firewall-app"
  network = google_compute_network.sobel_network.name

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }

  source_ranges = ["10.128.0.0/9"]
  target_tags   = ["sobel-worker"]
}

# RabbitMQ: accesible desde dentro de la red + SSH externo
resource "google_compute_firewall" "sobel_firewall_rabbitmq" {
  name    = "sobel-firewall-rabbitmq"
  network = google_compute_network.sobel_network.name

  allow {
    protocol = "tcp"
    ports    = ["5672", "15672", "22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["sobel-rabbitmq"]
}

# ─── SERVICE ACCOUNT ───────────────────────────────────────────
resource "google_service_account" "sobel_worker_sa" {
  account_id   = "sobel-worker-sa"
  display_name = "Sobel Worker Service Account"
  project      = var.project_id
}

# ─── RABBITMQ ──────────────────────────────────────────────────
resource "google_compute_instance" "rabbitmq" {
  name         = "sobel-rabbitmq"
  machine_type = "e2-medium"
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 21
    }
  }

  network_interface {
    network = google_compute_network.sobel_network.name
    access_config {}
  }

  metadata_startup_script = file("${path.module}/../scripts/bootstrap-rabbitmq.sh")

  service_account {
    email  = google_service_account.sobel_worker_sa.email
    scopes = ["cloud-platform"]
  }

  tags = ["sobel-rabbitmq"]
}

# ─── WORKERS ───────────────────────────────────────────────────
resource "google_compute_instance" "sobel_worker" {
  count        = var.worker_count
  name         = "sobel-worker-${count.index}"
  machine_type = var.machine_type
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 20
    }
  }

  network_interface {
    network = google_compute_network.sobel_network.name
    access_config {}
  }

  metadata_startup_script = templatefile("${path.module}/../scripts/bootstrap.sh", {
    worker_index  = count.index
    docker_image  = var.docker_image
    rabbitmq_host = google_compute_instance.rabbitmq.network_interface[0].network_ip
    rabbitmq_port = 5672
  })

  service_account {
    email  = google_service_account.sobel_worker_sa.email
    scopes = ["cloud-platform"]
  }

  labels = {
    environment = "production"
    managed_by  = "terraform"
    app         = "sobel"
  }

  tags = ["sobel-worker"]

  depends_on = [google_compute_instance.rabbitmq]
}
