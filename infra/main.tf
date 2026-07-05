# =========================================================================
# ACTIVATION LAYER FOR GOOGLE MANAGEMENT APIs
# =========================================================================

resource "google_project_service" "services" {
  for_each = toset([
    "compute.googleapis.com",          # Handles underlying cloud virtual networking
    "sqladmin.googleapis.com",         # Grants permission to provision Cloud SQL databases
    "run.googleapis.com",              # Activates the serverless Cloud Run engine
    "artifactregistry.googleapis.com", # Activates secure Docker image repository hosting
    "servicenetworking.googleapis.com", # Allows secure internal private database peering
    "vpcaccess.googleapis.com"
  ])

  service            = each.key
  disable_on_destroy = false # Prevents critical service disruptions when tearing down resources
}


# =========================================================================
# NETWORKING LAYER: ISOLATED ENTERPRISE VPC
# =========================================================================

# 1. Create the Custom Virtual Private Cloud (VPC)
resource "google_compute_network" "vpc_network" {
  name                    = "enterprise-rag-vpc"
  auto_create_subnetworks = false # Force manual subnetwork declaration for strict boundary control
  depends_on              = [google_project_service.services]
}

# 2. Declare a dedicated subnet for regional resources
resource "google_compute_subnetwork" "rag_subnet" {
  name          = "rag-compute-subnet"
  ip_cidr_range = "10.0.1.0/24" # Allocates 256 internal local IP addresses
  region        = var.gcp_region
  network       = google_compute_network.vpc_network.id
}

# =========================================================================
# PRIVATE SERVICES ACCESS (Peering Connection for Cloud SQL)
# =========================================================================

# 3. Reserve a dedicated internal IP range for Google Managed Services (Cloud SQL)
resource "google_compute_global_address" "private_ip_alloc" {
  name          = "rag-private-ip-alloc"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16 # Reserves a /16 block (10.X.0.0) so the DB can scale
  network       = google_compute_network.vpc_network.id
}

# 4. Establish the secure Private Peering Connection between your VPC and Google Services
resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc_network.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_alloc.name]
  deletion_policy         = "ABANDON"
}

# =========================================================================
# SERVERLESS VPC CONNECTOR (The Cloud Run to Database Bridge)
# =========================================================================

# 5. Create the physical bridge that lets serverless containers slide traffic into our VPC
resource "google_vpc_access_connector" "vpc_connector" {
  name          = "rag-vpc-connector"
  region        = var.gcp_region
  ip_cidr_range = "10.8.0.0/28" # Small routing range required exclusively by the connector
  network       = google_compute_network.vpc_network.name
  min_instances = 2
  max_instances = 3 # Constrained limits to prevent billing spikes
  depends_on    = [google_service_networking_connection.private_vpc_connection]
}


# =========================================================================
# STORAGE LAYER: MANAGED PRIVATE CLOUD SQL (POSTGRESQL)
# =========================================================================

# 1. Generate a randomized suffix to prevent database naming collisions on GCP
resource "random_id" "db_name_suffix" {
  byte_length = 4
}

# 2. Provision the Managed PostgreSQL Instance Core
resource "google_sql_database_instance" "postgres_instance" {
  name             = "rag-postgres-core-${random_id.db_name_suffix.hex}"
  database_version = "POSTGRES_15" # Version 15 natively supports the pgvector extension
  region           = var.gcp_region

  # Ensure the database isn't built until the private VPC connection network is fully wired
  depends_on = [google_service_networking_connection.private_vpc_connection]

  settings {
    tier            = "db-f1-micro" # Absolute lowest micro-spec compute tier for minimal costs
    disk_type       = "PD_HDD"      # Cost-effective standard magnetic drive storage
    disk_size       = 10            # 10 Gigabytes allocation limit (plenty for thousands of rows)
    disk_autoresize = false         # Turned OFF to prevent automatic scaling from blowing up budgets

    ip_configuration {
      ipv4_enabled                                  = false # Turned OFF to completely block public internet access
      private_network                               = google_compute_network.vpc_network.id
      enable_private_path_for_google_cloud_services = true
    }

    # Enterprise optimization parameters
    backup_configuration {
      enabled = false # Disabled for prototyping to save storage costs and maximize performance
    }
  }

  # Protection guardrail to prevent accidental terraform destroy commands from erasing your DB
  deletion_protection = false
}

# 3. Create the Logical Relational Database Registry
resource "google_sql_database" "vector_database" {
  name     = "vector_db" # Matches your local database name exactly for environment parity
  instance = google_sql_database_instance.postgres_instance.name
}

# 4. Create the Administrative Access User
resource "google_sql_user" "database_user" {
  name     = "postgres"
  instance = google_sql_database_instance.postgres_instance.name
  password = var.db_password # References the secure sensitive string from your tfvars file
}

# =========================================================================
# COMPONENT REGISTRY: GOOGLE ARTIFACT REGISTRY
# =========================================================================

# Provision a private repository to securely host our FastAPI Docker images
resource "google_artifact_registry_repository" "rag_repository" {
  location      = var.gcp_region
  repository_id = "enterprise-rag-repo"
  description   = "Secure private repository for enterprise RAG API Docker images"
  format        = "DOCKER"

  # Prevents registry creation from firing until the base API service is fully activated
  depends_on = [google_project_service.services]
}


# =========================================================================
# COMPUTE LAYER: SERVERLESS GOOGLE CLOUD RUN ENGINE
# =========================================================================

resource "google_cloud_run_v2_service" "api_service" {
  name     = "enterprise-rag-api"
  location = var.gcp_region
  ingress  = "INGRESS_TRAFFIC_ALL" # Allows public web browsers to hit our endpoints

  template {
    # Scale-to-0 Configuration optimization ($0 Idle Footprint)
    scaling {
      max_instance_count = 3 # Hard limit to prevent burst traffic billing spikes
      min_instance_count = 0 # If no requests hit the server, instances drop to 0, cost drops to $0
    }

    # Links this container directly to our private VPC Network Access connector
    vpc_access {
      connector = google_vpc_access_connector.vpc_connector.id
      egress    = "PRIVATE_RANGES_ONLY" # Only route local DB calls through the VPC; public APIs route over default paths
    }

    containers {
      image = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.rag_repository.repository_id}/api-service:v1.0"

      # Map container internal exposure port to match FastAPI's default 8000
      ports {
        container_port = 8000
      }

      # Inject live environment variables directly into our application code contracts
      env {
        name  = "DB_HOST"
        value = google_sql_database_instance.postgres_instance.private_ip_address
      }
      env {
        name  = "DB_PORT"
        value = "5432" # Standard internal PostgreSQL port
      }
      env {
        name  = "DB_NAME"
        value = google_sql_database.vector_database.name
      }
      env {
        name  = "DB_USER"
        value = google_sql_user.database_user.name
      }
      env {
        name  = "DB_PASSWORD"
        value = var.db_password
      }
      env {
        name  = "GITHUB_TOKEN"
        value = var.github_token
      }
    }
  }
}

# =========================================================================
# SECURITY LAYER: IAM UNAUTHENTICATED ACCESS POLICY
# =========================================================================

# Grant explicit permission to public internet users to hit our FastAPI web gateway
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  name     = google_cloud_run_v2_service.api_service.name
  location = google_cloud_run_v2_service.api_service.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}