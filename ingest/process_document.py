"""Lit un PDF de constat via Document AI et renvoie les champs structurés.

C'est l'étape qui, en production, peuple la table `sinistres` à partir des
pièces déposées par l'assuré. Dans ce projet de démo, la table est déjà
remplie par generate_data.py : ce script sert à VÉRIFIER que Document AI
extrait bien les valeurs qu'on a écrites dans les PDF.

Prérequis : créer un processeur Document AI (type "Form Parser" ou OCR) dans
la console, puis renseigner PROCESSOR_ID. Voir README étape 5.

    python process_document.py --project MON_PROJET --processor PROCESSOR_ID \
        --file ../data_generation/pdfs/S-500000.pdf
"""
import argparse

from google.api_core.client_options import ClientOptions
from google.cloud import documentai


def extraire(project: str, location: str, processor_id: str, fichier: str) -> dict:
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    name = client.processor_path(project, location, processor_id)

    with open(fichier, "rb") as f:
        contenu = f.read()

    raw = documentai.RawDocument(content=contenu, mime_type="application/pdf")
    result = client.process_document(
        request=documentai.ProcessRequest(name=name, raw_document=raw)
    )
    doc = result.document

    # Form Parser : on récupère les paires clé/valeur détectées.
    champs = {}
    for page in doc.pages:
        for field in page.form_fields:
            cle = _texte(field.field_name, doc.text).strip(" :\n")
            val = _texte(field.field_value, doc.text).strip()
            if cle:
                champs[cle] = val
    return {"texte_brut": doc.text, "champs": champs}


def champs_vers_sinistre(champs: dict) -> dict:
    """Mappe les paires clé/valeur d'un constat vers une ligne `sinistres`.

    Les libellés correspondent à ceux écrits par generate_data.py.
    """
    def get(*cles):
        for c in champs:
            if any(k.lower() in c.lower() for k in cles):
                return champs[c]
        return None

    montant_brut = (get("Montant") or "0").replace("EUR", "").replace("€", "").strip()
    try:
        montant = float(montant_brut.replace(",", "."))
    except ValueError:
        montant = 0.0

    return {
        "id_sinistre": get("N° sinistre", "N° de sinistre", "numero sinistre"),
        "num_police": get("police"),
        "date_sinistre": get("Date du sinistre", "date du"),
        "nature": (get("Nature") or "").strip(),
        "montant": montant,
        "tiers": None if (get("Tiers") in (None, "aucun")) else get("Tiers"),
        "description": get("Description"),
    }


def _texte(element, texte_complet: str) -> str:
    """Reconstitue le texte d'un élément à partir de ses offsets."""
    rep = ""
    for seg in element.text_anchor.text_segments:
        rep += texte_complet[int(seg.start_index) : int(seg.end_index)]
    return rep


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--location", default="eu")
    p.add_argument("--processor", required=True)
    p.add_argument("--file", required=True)
    args = p.parse_args()

    res = extraire(args.project, args.location, args.processor, args.file)
    print("Champs détectés :")
    for k, v in res["champs"].items():
        print(f"  {k!r} -> {v!r}")


if __name__ == "__main__":
    main()
