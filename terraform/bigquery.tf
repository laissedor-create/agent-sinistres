resource "google_bigquery_dataset" "assurance" {
  dataset_id  = var.dataset_id
  location    = var.region
  description = "Contrats et sinistres (données synthétiques)."

  depends_on = [google_project_service.enabled]
}

resource "google_bigquery_table" "contrats" {
  dataset_id          = google_bigquery_dataset.assurance.dataset_id
  table_id            = "contrats"
  deletion_protection = false

  schema = jsonencode([
    { name = "num_police", type = "STRING", mode = "REQUIRED" },
    { name = "nom_assure", type = "STRING", mode = "NULLABLE" },
    { name = "date_effet", type = "DATE", mode = "REQUIRED" },
    { name = "garanties", type = "STRING", mode = "REPEATED" },
    { name = "plafond", type = "NUMERIC", mode = "NULLABLE" },
    { name = "franchise", type = "NUMERIC", mode = "NULLABLE" },
    { name = "statut", type = "STRING", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "sinistres" {
  dataset_id          = google_bigquery_dataset.assurance.dataset_id
  table_id            = "sinistres"
  deletion_protection = false

  schema = jsonencode([
    { name = "id_sinistre", type = "STRING", mode = "REQUIRED" },
    { name = "num_police", type = "STRING", mode = "REQUIRED" },
    { name = "date_sinistre", type = "DATE", mode = "REQUIRED" },
    { name = "nature", type = "STRING", mode = "NULLABLE" },
    { name = "montant", type = "NUMERIC", mode = "NULLABLE" },
    { name = "tiers", type = "STRING", mode = "NULLABLE" },
    { name = "description", type = "STRING", mode = "NULLABLE" },
  ])
}
