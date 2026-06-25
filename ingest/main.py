"""Service Cloud Run déclenché par Eventarc quand un PDF arrive dans le bucket.

Reçoit l'événement Cloud Storage, télécharge le PDF, l'envoie à Document AI,
insère la ligne dans BigQuery, appelle l'agent pour obtenir une décision,
génère un PDF de décision et le dépose dans le dossier decisions/.
"""
import os
import tempfile

import process_document as docai
import requests
from fastapi import FastAPI, Request
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = FastAPI(title="Ingestion sinistres")

_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
_DATASET = os.environ.get("BQ_DATASET", "assurance")
_DOCAI_LOCATION = os.environ.get("DOCAI_LOCATION", "eu")
_PROCESSOR_ID = os.environ["DOCAI_PROCESSOR_ID"]
_AGENT_URL = os.environ.get("AGENT_URL", "")


@app.get("/")
def sante() -> dict:
    return {"status": "ok"}


def _pdf_decision(sinistre: dict, decision: str, chemin: str) -> None:
    """Génère un PDF de décision lisible."""
    c = canvas.Canvas(chemin, pagesize=A4)
    largeur, hauteur = A4
    y = hauteur - 72
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, y, "DÉCISION D'INSTRUCTION DE SINISTRE")
    c.setFont("Helvetica", 11)
    y -= 30
    c.drawString(72, y, f"Sinistre : {sinistre.get('id_sinistre')}")
    y -= 18
    c.drawString(72, y, f"Police : {sinistre.get('num_police')}")
    y -= 18
    c.drawString(72, y, f"Nature : {sinistre.get('nature')}")
    y -= 30
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "Décision de l'agent :")
    c.setFont("Helvetica", 10)
    y -= 22
    # On découpe le texte de la décision en lignes pour qu'il tienne dans la page.
    for ligne_brute in (decision or "Aucune décision.").split("\n"):
        ligne = ligne_brute.replace("**", "").replace("*", "-")
        while len(ligne) > 95:
            c.drawString(72, y, ligne[:95])
            ligne = ligne[95:]
            y -= 14
            if y < 72:
                c.showPage()
                y = hauteur - 72
                c.setFont("Helvetica", 10)
        c.drawString(72, y, ligne)
        y -= 14
        if y < 72:
            c.showPage()
            y = hauteur - 72
            c.setFont("Helvetica", 10)
    c.save()


@app.post("/")
async def sur_depot_pdf(request: Request) -> dict:
    event = await request.json()
    bucket = event.get("bucket")
    nom = event.get("name", "")

    # On ignore tout ce qui n'est pas un constat (évite de retraiter nos propres décisions).
    if not nom.lower().endswith(".pdf"):
        return {"ignore": f"pas un PDF : {nom}"}
    if nom.startswith("decisions/"):
        return {"ignore": "fichier de décision, ignoré"}

    from google.cloud import bigquery, storage

    storage_client = storage.Client(project=_PROJECT)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        storage_client.bucket(bucket).blob(nom).download_to_filename(tmp.name)
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
            print(f"DECISION pour {sinistre['id_sinistre']} obtenue")
        except Exception as e:
            print(f"Erreur appel agent : {e}")

    # Génération du PDF de décision et dépôt dans decisions/
    pdf_uri = None
    if decision:
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as out:
                _pdf_decision(sinistre, decision, out.name)
                cible = f"decisions/decision-{sinistre['id_sinistre']}.pdf"
                storage_client.bucket(bucket).blob(cible).upload_from_filename(out.name)
                pdf_uri = f"gs://{bucket}/{cible}"
                print(f"PDF de décision déposé : {pdf_uri}")
        except Exception as e:
            print(f"Erreur génération PDF : {e}")

    return {
        "ok": True,
        "id_sinistre": sinistre["id_sinistre"],
        "decision_obtenue": decision is not None,
        "pdf_decision": pdf_uri,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
