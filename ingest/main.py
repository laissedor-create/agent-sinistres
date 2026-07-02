"""Service Cloud Run déclenché par Eventarc quand un PDF arrive dans le bucket.

Trace le parcours de chaque dossier dans la table suivi_dossiers :
reçu -> extrait -> décidé, puis génère le PDF de décision.
"""
import datetime
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


def log_statut(id_sinistre, statut, etape=None, detail=None):
    """Écrit une ligne de suivi dans BigQuery (journal de bord du dossier)."""
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=_PROJECT)
        ligne = {
            "id_sinistre": id_sinistre,
            "statut": statut,
            "etape": etape,
            "horodatage": datetime.datetime.utcnow().isoformat(),
            "detail": detail,
        }
        client.insert_rows_json(f"{_PROJECT}.{_DATASET}.suivi_dossiers", [ligne])
        print(f"SUIVI {id_sinistre} -> {statut}")
    except Exception as e:
        print(f"Erreur log_statut : {e}")


@app.get("/")
def sante() -> dict:
    return {"status": "ok"}


def _saut_page(c, y, hauteur):
    if y < 72:
        c.showPage()
        c.setFont("Helvetica", 10)
        return hauteur - 72
    return y


def _pdf_decision(sinistre, decision, chemin):
    c = canvas.Canvas(chemin, pagesize=A4)
    _, hauteur = A4
    y = hauteur - 72
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, y, "DÉCISION D'INSTRUCTION DE SINISTRE")
    c.setFont("Helvetica", 11)
    for label in [f"Sinistre : {sinistre.get('id_sinistre')}",
                  f"Police : {sinistre.get('num_police')}",
                  f"Nature : {sinistre.get('nature')}"]:
        y -= 18
        c.drawString(72, y, label)
    y -= 30
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "Décision de l'agent :")
    c.setFont("Helvetica", 10)
    y -= 22
    for ligne_brute in (decision or "Aucune décision.").split("\n"):
        ligne = ligne_brute.replace("**", "").replace("*", "-")
        while len(ligne) > 95:
            c.drawString(72, y, ligne[:95])
            ligne = ligne[95:]
            y -= 14
            y = _saut_page(c, y, hauteur)
        c.drawString(72, y, ligne)
        y -= 14
        y = _saut_page(c, y, hauteur)
    c.save()


@app.post("/")
async def sur_depot_pdf(request: Request) -> dict:
    event = await request.json()
    bucket = event.get("bucket")
    nom = event.get("name", "")

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

    id_s = sinistre["id_sinistre"]
    log_statut(id_s, "reçu", "depot", detail=nom)

    client = bigquery.Client(project=_PROJECT)
    errors = client.insert_rows_json(f"{_PROJECT}.{_DATASET}.sinistres", [sinistre])
    if errors:
        return {"erreur": str(errors)}
    log_statut(id_s, "extrait", "document_ai",
               detail=f"{sinistre.get('nature')} · {sinistre.get('montant')} EUR")

    decision = None
    if _AGENT_URL:
        try:
            reponse = requests.post(
                f"{_AGENT_URL}/instruire",
                json={"num_police": sinistre["num_police"], "id_sinistre": id_s},
                timeout=120,
            )
            reponse.raise_for_status()
            decision = reponse.json().get("decision")
            log_statut(id_s, "instruit", "agent")
        except Exception as e:
            print(f"Erreur appel agent : {e}")
            log_statut(id_s, "erreur", "agent", detail=str(e))

    pdf_uri = None
    if decision:
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as out:
                _pdf_decision(sinistre, decision, out.name)
                cible = f"decisions/decision-{id_s}.pdf"
                storage_client.bucket(bucket).blob(cible).upload_from_filename(out.name)
                pdf_uri = f"gs://{bucket}/{cible}"
            log_statut(id_s, "décidé", "archivage", detail=pdf_uri)
        except Exception as e:
            print(f"Erreur génération PDF : {e}")

    return {"ok": True, "id_sinistre": id_s, "decision_obtenue": decision is not None, "pdf_decision": pdf_uri}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
