output "project_number" {
  value       = data.google_project.this.number
  description = "Numéro du projet (utile pour le provider WIF)."
}

output "workload_identity_provider" {
  value       = "projects/${data.google_project.this.number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github.workload_identity_pool_id}/providers/${google_iam_workload_identity_pool_provider.github.workload_identity_pool_provider_id}"
  description = "À copier dans le secret GitHub WIF_PROVIDER."
}

output "deployer_service_account" {
  value       = google_service_account.deployer.email
  description = "À copier dans le secret GitHub WIF_SERVICE_ACCOUNT."
}

output "runtime_service_account" {
  value = google_service_account.runtime.email
}

output "cloud_run_url" {
  value = google_cloud_run_v2_service.agent.uri
}

output "documentai_processor_id" {
  value       = google_document_ai_processor.form_parser.name
  description = "ID du processeur Document AI (déjà injecté dans le service d'ingestion)."
}

output "artifact_registry" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

data "google_project" "this" {
  project_id = var.project_id
}
