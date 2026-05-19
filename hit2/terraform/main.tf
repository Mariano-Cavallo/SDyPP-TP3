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

  source_ranges = ["10.128.0.0/9"]  # rango interno de GCP auto-subnet
  target_tags   = ["sobel-worker"]
}

# ─── SERVICE ACCOUNT ───────────────────────────────────────────
resource "google_service_account" "sobel_worker_sa" {
  account_id   = "sobel-worker-sa"
  display_name = "Sobel Worker Service Account"
  project      = var.project_id
}

resource "google_project_iam_member" "sobel_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.sobel_worker_sa.email}"
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
    worker_index   = count.index
    docker_image   = var.docker_image
    rabbitmq_host  = var.rabbitmq_host
    rabbitmq_port  = var.rabbitmq_port
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
}