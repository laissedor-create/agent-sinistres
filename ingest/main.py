"""Service Cloud Run déclenché par Eventarc quand un PDF arrive dans le bucket.

Reçoit l'événement Cloud Storage, télécharge le PDF, l'envoie à Document AI,
insère la ligne dans BigQuery, puis appelle l'agent pour obtenir une décision.
"""
from __future__ import annotations

import os
import tempfile

import process_document as docai
import requests
from fastapi import FastAPI, Request

app = FastAPI(title="Ingestion sinistres")

_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
_DATASET = os.environ.get("BQ_DATASET", "assurance")
_DOCAI_LOCATION = os.environ.get("DOCAI_LOCATION", "eu")
_PROCESSOR_ID = os.environ["DOCAI_PROCESSOR_ID"]
_AGENT_URL = os.environ.get("AGENT_URL", "")


@app.get("/")
def sante() -> dict:
    return {"status": "ok"}


@app.post("/")
async def sur_depot_pdf(request: Request) -> dict:
    event = await request.json()
    bucket = event.get("bucket")
    nom = event.get("name", "")

    if not nom.lower().endswith(".pdf"):
        return {"ignore": f"pas un PDF : {nom}"}

    from google.cloud import bigquery, storage

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        storage.Client(project=_PROJECT).bucket(bucket).blob(nom).download_to_filename(tmp.name)
        chemin = tmp.name

    res = docai.extraire(_PROJECT, _DOCAI_LOCATION, _PROCESSOR_ID, chemin)
    sinistre = docai.champs_vers_sinistre(res["champs"])

    if not sinistre.get("id_sinistre") or not sinistre.get("num_police"):
        return {"erreur": "champs obligatoires manquants", "champs": res["champs"]}

    client = bigquery.Client(project=_PROJECT)
    table_id = f"{_PROJECT}.{_DATASET}.sinistres"
    errors = client.insert_rows_json(table_id, [sinistre])
    if errors:
        return {"erreur": str(errors)}

    decision = None
    if _AGENT_URL:
        try:
            reponse = requests.post(
                f"{_AGENT_URL}/instruire",
                json={
                    "num_police": sinistre["num_police"],
                    "id_sinistre": sinistre["id_sinistre"],
                },
                timeout=120,
            )
            reponse.raise_for_status()
            decision = reponse.json().get("decision")
            print(f"DECISION pour {sinistre['id_sinistre']} :\n{decision}")
        except Exception as e:
            print(f"Erreur appel agent : {e}")

    return {
        "ok": True,
        "id_sinistre": sinistre["id_sinistre"],
        "fichier": nom,
        "decision_obtenue": decision is not None,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
