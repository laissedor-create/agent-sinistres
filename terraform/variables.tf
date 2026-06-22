variable "project_id" {
  type        = string
  description = "ID du projet GCP (ex: assurance-agent-123456)."
}

variable "region" {
  type        = string
  description = "Région GCP."
  default     = "europe-west1"
}

variable "github_repo" {
  type        = string
  description = "Dépôt GitHub autorisé pour le CI/CD, au format 'owner/repo'."
}

variable "dataset_id" {
  type        = string
  description = "ID du dataset BigQuery."
  default     = "assurance"
}

variable "service_name" {
  type        = string
  description = "Nom du service Cloud Run."
  default     = "agent-sinistres"
}
