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