"""Service Cloud Run déclenché par Eventarc quand un PDF arrive dans le bucket.

Reçoit l'événement Cloud Storage (object.finalized), télécharge le PDF,
l'envoie à Document AI, puis insère la ligne extraite dans BigQuery.
"""
from __future__ import annotations

import os
import tempfile

import process_document as docai
from fastapi import FastAPI, Request

app = FastAPI(title="Ingestion sinistres")

_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
_DATASET = os.environ.get("BQ_DATASET", "assurance")
_DOCAI_LOCATION = os.environ.get("DOCAI_LOCATION", "eu")
_PROCESSOR_ID = os.environ["DOCAI_PROCESSOR_ID"]


@app.get("/")
def sante() -> dict:
    return {"status": "ok"}


@app.post("/")
async def sur_depot_pdf(request: Request) -> dict:
    # Eventarc livre l'événement GCS en JSON : { bucket, name, ... }
    event = await request.json()
    bucket = event.get("bucket")
    nom = event.get("name", "")

    if not nom.lower().endswith(".pdf"):
        return {"ignore": f"pas un PDF : {nom}"}

    from google.cloud import bigquery, storage

    # 1. Télécharger le PDF
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        storage.Client(project=_PROJECT).bucket(bucket).blob(nom).download_to_filename(tmp.name)
        chemin = tmp.name

    # 2. Extraire les champs via Document AI
    res = docai.extraire(_PROJECT, _DOCAI_LOCATION, _PROCESSOR_ID, chemin)
    sinistre = docai.champs_vers_sinistre(res["champs"])

    if not sinistre.get("id_sinistre") or not sinistre.get("num_police"):
        return {"erreur": "champs obligatoires manquants", "champs": res["champs"]}

    # 3. Insérer dans BigQuery
    client = bigquery.Client(project=_PROJECT)
    table_id = f"{_PROJECT}.{_DATASET}.sinistres"
    errors = client.insert_rows_json(table_id, [sinistre])
    if errors:
        return {"erreur": str(errors)}

    return {"ok": True, "id_sinistre": sinistre["id_sinistre"], "fichier": nom}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
