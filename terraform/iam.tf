# --- Compte de service exécuté PAR l'agent sur Cloud Run (runtime) ---
resource "google_service_account" "runtime" {
  account_id   = "agent-runtime"
  display_name = "Agent sinistres - runtime Cloud Run"
}

# L'agent a besoin de lire BigQuery, d'appeler Vertex AI et Document AI.
locals {
  runtime_roles = [
    "roles/bigquery.dataViewer",
    "roles/bigquery.dataEditor", # l'ingestion insère les sinistres extraits
    "roles/bigquery.jobUser",
    "roles/aiplatform.user",
    "roles/documentai.apiUser",
    "roles/storage.objectViewer",
  ]
}

resource "google_project_iam_member" "runtime" {
  for_each = toset(local.runtime_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.runtime.email}"
}

# --- Compte de service utilisé PAR GitHub Actions (déploiement) ---
resource "google_service_account" "deployer" {
  account_id   = "github-deployer"
  display_name = "GitHub Actions - déploiement"
}

locals {
  deployer_roles = [
    "roles/run.admin",                 # déployer sur Cloud Run
    "roles/artifactregistry.writer",   # pousser les images
    "roles/iam.serviceAccountUser",    # agir en tant que runtime SA
    "roles/cloudbuild.builds.editor",  # builds
    "roles/storage.admin",             # logs/artefacts de build
  ]
}

resource "google_project_iam_member" "deployer" {
  for_each = toset(local.deployer_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.deployer.email}"
}
