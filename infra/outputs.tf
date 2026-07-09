output "artifact_registry_repository_url" {
  value       = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.rag_repository.repository_id}"
  description = "The exact remote URL target for tagging and pushing your local Docker image"
}

output "database_private_ip" {
  value       = google_sql_database_instance.postgres_instance.private_ip_address
  description = "The private internal IP address of the PostgreSQL database instance inside the VPC"
}

output "database_connection_name" {
  value       = google_sql_database_instance.postgres_instance.connection_name
  description = "The global cloud instance connection name used for secure remote proxy handshakes"
}

output "production_api_url" {
  value       = google_cloud_run_v2_service.api_service.uri
  description = "The live public production URL endpoint assigned to your serverless FastAPI RAG framework"
}