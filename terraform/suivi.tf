resource "google_bigquery_table" "suivi_dossiers" {
  dataset_id          = google_bigquery_dataset.assurance.dataset_id
  table_id            = "suivi_dossiers"
  deletion_protection = false

  schema = jsonencode([
    { name = "id_sinistre", type = "STRING", mode = "REQUIRED" },
    { name = "statut", type = "STRING", mode = "REQUIRED" },
    { name = "etape", type = "STRING", mode = "NULLABLE" },
    { name = "horodatage", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "detail", type = "STRING", mode = "NULLABLE" },
  ])
}
