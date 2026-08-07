variable "gcp_project_id" {
  type        = string
  description = "The unique ID of your Google Cloud Platform project"
}

variable "gcp_region" {
  type        = string
  default     = "us-central1"
  description = "The target cloud data center region for deployment"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "The administrative root user password for Google Cloud SQL"
}

variable "github_token" {
  type        = string
  sensitive   = true
  description = "The live GitHub Models authorization token used by the RAG orchestrator"
}

variable "db_user" {
  type        = string
  default     = "postgres"
  description = "Standard database user aligned with env contract"
}

variable "db_name" {
  type        = string
  default     = "enterprise_rag_db"
  description = "Standard database name aligned with env contract"
}

variable "app_env" {
  type        = string
  default     = "PRODUCTION"
  description = "The explicit runtime environment for the FastAPI backend"
}

variable "api_key" {
  type        = string
  sensitive   = true
  description = "The core X-API-Key used to authenticate requests to the FastAPI backend"
}