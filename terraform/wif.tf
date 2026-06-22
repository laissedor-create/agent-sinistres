# Permet à GitHub Actions de s'authentifier SANS clé JSON, via OIDC.
# GitHub présente un jeton OIDC ; GCP l'échange contre un jeton court (15 min).

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub Actions pool"

  depends_on = [google_project_service.enabled]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub provider"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }

  # Condition OBLIGATOIRE depuis 2023 : restreint au dépôt autorisé.
  attribute_condition = "assertion.repository == '${var.github_repo}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Autorise SEULEMENT ton dépôt à emprunter le compte de service "deployer".
resource "google_service_account_iam_member" "wif_deployer" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}
