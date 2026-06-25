"""Outils que l'agent Gemini peut appeler.

Deux familles :
- accès aux données (BigQuery) : get_contrat, get_sinistre
- règles métier pures (testables sans GCP) : check_eligibilite, detect_anomalie,
  search_conditions

Toutes les fonctions ont des annotations de type et une docstring : le SDK
google-genai s'en sert pour générer automatiquement le schéma des outils.
"""

import datetime as dt
import logging
import os

# Correspondance nature -> code de garantie (doit refléter generate_data.py).
NATURE_VERS_GARANTIE = {
    "dégât des eaux": "DDE",
    "incendie": "INCENDIE",
    "vol": "VOL",
    "bris de glace": "BDG",
    "catastrophe naturelle": "CATNAT",
}

_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
_DATASET = os.environ.get("BQ_DATASET", "assurance")


def _bq():
    from google.cloud import bigquery

    return bigquery.Client(project=_PROJECT)


def get_contrat(num_police: str) -> dict:
    """Récupère un contrat d'assurance par son numéro de police.

    Args:
        num_police: numéro de police, ex. "P-100001".

    Returns:
        Un dict avec les garanties, le plafond, la franchise, la date d'effet
        et le statut ; ou {"trouve": False} si le contrat n'existe pas.
    """
    client = _bq()
    query = f"""
        SELECT num_police, nom_assure, CAST(date_effet AS STRING) AS date_effet,
               garanties, CAST(plafond AS FLOAT64) AS plafond,
               CAST(franchise AS FLOAT64) AS franchise, statut
        FROM `{_PROJECT}.{_DATASET}.contrats`
        WHERE num_police = @p
        LIMIT 1
    """
    from google.cloud import bigquery

    try:
        job = client.query(
            query,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("p", "STRING", num_police)]
            ),
        )
        rows = list(job.result())
    except Exception as e:
        logging.exception("ERREUR get_contrat")
        return {"trouve": False, "erreur": str(e), "num_police": num_police}
    if not rows:
        return {"trouve": False, "num_police": num_police}
    r = dict(rows[0])
    r["trouve"] = True
    return r


def get_sinistre(id_sinistre: str) -> dict:
    """Récupère un sinistre déclaré par son identifiant.

    Args:
        id_sinistre: identifiant du sinistre, ex. "S-500000".

    Returns:
        Un dict avec la nature, le montant, la date et la police liée ;
        ou {"trouve": False} si le sinistre n'existe pas.
    """
    client = _bq()
    query = f"""
        SELECT id_sinistre, num_police, CAST(date_sinistre AS STRING) AS date_sinistre,
               nature, CAST(montant AS FLOAT64) AS montant, tiers, description
        FROM `{_PROJECT}.{_DATASET}.sinistres`
        WHERE id_sinistre = @s
        LIMIT 1
    """
    from google.cloud import bigquery

    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("s", "STRING", id_sinistre)]
        ),
    )
    rows = list(job.result())
    if not rows:
        return {"trouve": False, "id_sinistre": id_sinistre}
    r = dict(rows[0])
    r["trouve"] = True
    return r


def check_eligibilite(
    nature: str, montant: float, garanties: list[str], plafond: float, franchise: float
) -> dict:
    """Détermine si un sinistre est couvert et calcule le remboursement.

    Args:
        nature: nature du sinistre (ex. "dégât des eaux").
        montant: montant déclaré en euros.
        garanties: liste des codes de garanties du contrat.
        plafond: plafond d'indemnisation du contrat.
        franchise: franchise du contrat.

    Returns:
        Un dict : couvert (bool), remboursement (float), motif (str).
    """
    code = NATURE_VERS_GARANTIE.get(nature.lower())
    if code is None:
        return {"couvert": False, "remboursement": 0.0, "motif": f"Nature inconnue : {nature}"}
    if code not in garanties:
        return {
            "couvert": False,
            "remboursement": 0.0,
            "motif": f"Garantie {code} non souscrite",
        }
    if montant <= franchise:
        return {
            "couvert": True,
            "remboursement": 0.0,
            "motif": f"Montant ({montant}) inférieur à la franchise ({franchise})",
        }
    remboursement = min(montant - franchise, plafond)
    return {
        "couvert": True,
        "remboursement": round(remboursement, 2),
        "motif": f"Couvert : {montant} - franchise {franchise}, plafonné à {plafond}",
    }


def detect_anomalie(
    date_effet: str, date_sinistre: str, montant: float, plafond: float
) -> dict:
    """Repère des signaux de fraude ou d'incohérence à vérifier manuellement.

    Args:
        date_effet: date d'effet du contrat (AAAA-MM-JJ).
        date_sinistre: date du sinistre (AAAA-MM-JJ).
        montant: montant déclaré.
        plafond: plafond du contrat.

    Returns:
        Un dict : suspect (bool), signaux (liste de str).
    """
    signaux: list[str] = []
    d_effet = dt.date.fromisoformat(date_effet)
    d_sin = dt.date.fromisoformat(date_sinistre)

    if d_sin < d_effet:
        signaux.append("Sinistre antérieur à la date d'effet du contrat")
    elif (d_sin - d_effet).days < 30:
        signaux.append("Sinistre déclaré moins de 30 jours après la souscription")
    if plafond and montant >= 0.9 * plafond:
        signaux.append("Montant proche ou au-delà du plafond")

    return {"suspect": len(signaux) > 0, "signaux": signaux}


# Base de connaissances minimale (conditions générales). En production,
# remplacer par un appel à Vertex AI Search pour un vrai RAG.
_CONDITIONS = {
    "DDE": "Les dégâts des eaux sont couverts hors négligence caractérisée. Franchise applicable.",
    "VOL": "Le vol est couvert sur présentation d'un dépôt de plainte sous 48h.",
    "INCENDIE": "L'incendie est couvert sauf cause volontaire de l'assuré.",
    "BDG": "Le bris de glace couvre les vitrages du logement principal.",
    "CATNAT": "Garantie déclenchée uniquement après arrêté de catastrophe naturelle.",
}


def search_conditions(question: str) -> dict:
    """Recherche une clause dans les conditions générales.

    Args:
        question: question en langage naturel sur une garantie.

    Returns:
        Un dict : extraits (liste de clauses pertinentes).
    """
    q = question.lower()
    extraits = [
        texte
        for code, texte in _CONDITIONS.items()
        if code.lower() in q or any(mot in q for mot in texte.lower().split()[:3])
    ]
    if not extraits:
        extraits = list(_CONDITIONS.values())
    return {"extraits": extraits}
