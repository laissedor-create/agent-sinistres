# Dépôt d'images Docker pour Cloud Run.
resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = "agent-sinistres"
  format        = "DOCKER"
  description   = "Images de l'agent sinistres."

  depends_on = [google_project_service.enabled]
}
