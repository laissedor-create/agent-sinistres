# Bucket où les assurés déposent les pièces du sinistre (constats, factures PDF).
resource "google_storage_bucket" "sinistres" {
  name                        = "${var.project_id}-sinistres"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true # projet d'apprentissage : on autorise la suppression

  depends_on = [google_project_service.enabled]
}
