terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Le state est stocké dans un bucket GCS (créé une seule fois, voir README étape 3).
  # On le laisse en commentaire au premier "init" local, puis on l'active.
  # backend "gcs" {
  #   bucket = "REMPLACER-PAR-VOTRE-BUCKET-TFSTATE"
  #   prefix = "agent-sinistres"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
