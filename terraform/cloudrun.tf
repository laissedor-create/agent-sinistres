# Service Cloud Run qui héberge l'API de l'agent.
# L'image est poussée par le CI ; au 1er apply elle n'existe pas encore,
# donc on utilise une image "hello" par défaut, remplacée ensuite par le déploiement.
resource "google_cloud_run_v2_service" "agent" {
  name     = var.service_name
  location = var.region

  deletion_protection = false

  template {
    service_account = google_service_account.runtime.email

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "BQ_DATASET"
        value = var.dataset_id
      }
    }
  }

  # Le CI met à jour l'image ; on demande à Terraform d'ignorer ce champ
  # pour ne pas écraser le déploiement à chaque "apply".
  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [google_project_iam_member.runtime]
}

# Accès public à l'API (à restreindre en production).
resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.agent.name
  location = google_cloud_run_v2_service.agent.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
