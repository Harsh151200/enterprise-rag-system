# =========================================================================
# ACTIVATION LAYER FOR GOOGLE MANAGEMENT APIs
# =========================================================================

resource "google_project_service" "services" {
  for_each = toset([
    "compute.googleapis.com",          
    "sqladmin.googleapis.com",         
    "run.googleapis.com",              
    "artifactregistry.googleapis.com", 
    "servicenetworking.googleapis.com", 
    "vpcaccess.googleapis.com",
    "secretmanager.googleapis.com"     # NEW: Activates the Secret Manager API
  ])

  service            = each.key
  disable_on_destroy = false 
}

# =========================================================================
# SECRETS MANAGEMENT LAYER (NEW)
# =========================================================================

# 1. Vault for Database Password
resource "google_secret_manager_secret" "db_password" {
  secret_id = "rag-db-password"
  replication {
    auto {}
  }
  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "db_password_version" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = var.db_password
}

# 2. Vault for GitHub Models Token
resource "google_secret_manager_secret" "github_token" {
  secret_id = "rag-github-token"
  replication {
    auto {}
  }
  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "github_token_version" {
  secret      = google_secret_manager_secret.github_token.id
  secret_data = var.github_token
}

# =========================================================================
# IAM SECURITY: DEDICATED CLOUD RUN SERVICE ACCOUNT (NEW)
# =========================================================================

# Creates a unique identity for Cloud Run to operate under
resource "google_service_account" "cloudrun_sa" {
  account_id   = "enterprise-rag-run-sa"
  display_name = "Cloud Run Service Account for RAG System"
}

# Grants the Cloud Run identity permission to read the DB password vault
resource "google_secret_manager_secret_iam_member" "db_pwd_access" {
  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}

# Grants the Cloud Run identity permission to read the GitHub token vault
resource "google_secret_manager_secret_iam_member" "gh_token_access" {
  secret_id = google_secret_manager_secret.github_token.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}

# =========================================================================
# NETWORKING LAYER: ISOLATED ENTERPRISE VPC
# =========================================================================

resource "google_compute_network" "vpc_network" {
  name                    = "enterprise-rag-vpc"
  auto_create_subnetworks = false 
  depends_on              = [google_project_service.services]
}

resource "google_compute_subnetwork" "rag_subnet" {
  name          = "rag-compute-subnet"
  ip_cidr_range = "10.0.1.0/24" 
  region        = var.gcp_region
  network       = google_compute_network.vpc_network.id
}

resource "google_compute_global_address" "private_ip_alloc" {
  name          = "rag-private-ip-alloc"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16 
  network       = google_compute_network.vpc_network.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc_network.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_alloc.name]
  deletion_policy         = "ABANDON"
}


# resource "google_vpc_access_connector" "vpc_connector" {
#   name          = "rag-vpc-connector"
#   region        = var.gcp_region
#   ip_cidr_range = "10.8.0.0/28" 
#   network       = google_compute_network.vpc_network.name
#   min_instances = 2
#   max_instances = 3 
#   depends_on    = [google_service_networking_connection.private_vpc_connection]
# }


# =========================================================================
# STORAGE LAYER: MANAGED PRIVATE CLOUD SQL (POSTGRESQL)
# =========================================================================

resource "random_id" "db_name_suffix" {
  byte_length = 4
}

resource "google_sql_database_instance" "postgres_instance" {
  name             = "rag-postgres-core-${random_id.db_name_suffix.hex}"
  database_version = "POSTGRES_15" 
  region           = var.gcp_region
  depends_on       = [google_service_networking_connection.private_vpc_connection]

  settings {
    tier              = "db-f1-micro" 
    disk_type         = "PD_HDD"      
    disk_size         = 10            
    disk_autoresize   = false         

    ip_configuration {
      ipv4_enabled                                  = false 
      private_network                               = google_compute_network.vpc_network.id
      enable_private_path_for_google_cloud_services = true
    }

    backup_configuration {
      enabled = false 
    }
  }

  deletion_protection = false

  # Gives the shared-core micro engine extra breathing room to coordinate 
  # private VPC IP mappings without causing client-side abort errors.
  timeouts {
    create = "30m"
  }
}

resource "google_sql_database" "vector_database" {
  name     = var.db_name
  instance = google_sql_database_instance.postgres_instance.name
}

resource "google_sql_user" "database_user" {
  name     = var.db_user
  instance = google_sql_database_instance.postgres_instance.name
  password = var.db_password 
}

# =========================================================================
# COMPONENT REGISTRY: GOOGLE ARTIFACT REGISTRY
# =========================================================================

resource "google_artifact_registry_repository" "rag_repository" {
  location      = var.gcp_region
  repository_id = "enterprise-rag-repo"
  description   = "Secure private repository for enterprise RAG API Docker images"
  format        = "DOCKER"
  depends_on    = [google_project_service.services]
}

# =========================================================================
# COMPUTE LAYER: SERVERLESS GOOGLE CLOUD RUN ENGINE
# =========================================================================

resource "google_cloud_run_v2_service" "api_service" {
  name     = "enterprise-rag-api"
  location = var.gcp_region
  ingress  = "INGRESS_TRAFFIC_ALL" 

  template {
    # NEW: Binds the custom Service Account to this container
    service_account = google_service_account.cloudrun_sa.email

    scaling {
      max_instance_count = 3 
      min_instance_count = 0 
    }

    vpc_access {
      network_interfaces {
        network    = google_compute_network.vpc_network.id
        subnetwork = google_compute_subnetwork.rag_subnet.id
      }
      egress = "PRIVATE_RANGES_ONLY" 
    }

    containers {
      image = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.rag_repository.repository_id}/api-service:v3.0"

      # NEW: Grants enough RAM to hold PyTorch and SentenceTransformer in memory
      resources {
        limits = {
          memory = "2Gi"
          cpu    = "2"
        }
      }

      ports {
        container_port = 8000
      }

      # Standard environment variables...
      env {
        # NEW: Explicitly signals the backend to load ProductionConfig
        name  = "APP_ENV"
        value = var.app_env
      }
      env {
        name  = "DB_HOST"
        value = google_sql_database_instance.postgres_instance.private_ip_address
      }
      env {
        name  = "DB_PORT"
        value = "5432" # Standard canonical Postgres port
      }
      env {
        name  = "DB_NAME"
        value = google_sql_database.vector_database.name
      }
      env {
        name  = "DB_USER"
        value = google_sql_user.database_user.name
      }

      # Secrets Manager references...
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GITHUB_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.github_token.secret_id
            version = "latest"
          }
        }
      }
    }
  }
}

# =========================================================================
# SECURITY LAYER: IAM UNAUTHENTICATED ACCESS POLICY
# =========================================================================

resource "google_cloud_run_v2_service_iam_member" "public_access" {
  name     = google_cloud_run_v2_service.api_service.name
  location = google_cloud_run_v2_service.api_service.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}