# Active toutes les APIs nécessaires au projet.
locals {
  apis = [
    "run.googleapis.com",              # Cloud Run
    "aiplatform.googleapis.com",       # Vertex AI / Gemini
    "documentai.googleapis.com",       # Document AI
    "bigquery.googleapis.com",         # BigQuery
    "storage.googleapis.com",          # Cloud Storage
    "artifactregistry.googleapis.com", # images Docker
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",   # Workload Identity Federation
    "cloudbuild.googleapis.com",       # build des images en CI
    "eventarc.googleapis.com",         # déclencheur sur dépôt de PDF
    "pubsub.googleapis.com",           # transport des événements
  ]
}

resource "google_project_service" "enabled" {
  for_each = toset(local.apis)
  service  = each.value

  disable_on_destroy = false
}
