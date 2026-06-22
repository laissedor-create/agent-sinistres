# --- Service Cloud Run d'ingestion (déclenché par Eventarc, NON public) ---
resource "google_cloud_run_v2_service" "ingest" {
  name                = "ingest-sinistres"
  location            = var.region
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
        name  = "BQ_DATASET"
        value = var.dataset_id
      }
      env {
        name  = "DOCAI_LOCATION"
        value = "eu"
      }
      env {
        name  = "DOCAI_PROCESSOR_ID"
        value = google_document_ai_processor.form_parser.name
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [google_project_iam_member.runtime]
}

# --- Permissions Eventarc ---

# Compte de service qui porte le déclencheur.
resource "google_service_account" "eventarc" {
  account_id   = "eventarc-trigger"
  display_name = "Eventarc - déclencheur ingestion"
}

resource "google_project_iam_member" "eventarc_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.eventarc.email}"
}

# Le déclencheur doit pouvoir invoquer le service d'ingestion.
resource "google_cloud_run_v2_service_iam_member" "eventarc_invoker" {
  name     = google_cloud_run_v2_service.ingest.name
  location = google_cloud_run_v2_service.ingest.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.eventarc.email}"
}

# Le compte de service Cloud Storage doit pouvoir publier les événements.
data "google_storage_project_service_account" "gcs" {}

resource "google_project_iam_member" "gcs_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${data.google_storage_project_service_account.gcs.email_address}"
}

# --- Le déclencheur : dépôt d'objet dans le bucket -> service d'ingestion ---
resource "google_eventarc_trigger" "pdf_depose" {
  name            = "sinistre-pdf-depose"
  location        = var.region
  service_account = google_service_account.eventarc.email

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }
  matching_criteria {
    attribute = "bucket"
    value     = google_storage_bucket.sinistres.name
  }

  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.ingest.name
      region  = var.region
      path    = "/"
    }
  }

  depends_on = [
    google_project_iam_member.eventarc_receiver,
    google_project_iam_member.gcs_pubsub_publisher,
    google_cloud_run_v2_service_iam_member.eventarc_invoker,
  ]
}
