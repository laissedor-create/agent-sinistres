"""Génère des données synthétiques cohérentes pour le projet :
- table BigQuery `contrats`
- table BigQuery `sinistres` (cohérente avec les contrats)
- des PDF de constats/factures déposés dans Cloud Storage (pour Document AI)

Lance-le depuis Cloud Shell (zéro install) ou en local dans un venv :
    python generate_data.py --project MON_PROJET --bucket MON_BUCKET-sinistres
"""
import argparse
import datetime as dt
import os
import random

from faker import Faker
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

fake = Faker("fr_FR")
Faker.seed(42)
random.seed(42)

# Correspondance nature du sinistre -> code de garantie.
NATURES = {
    "dégât des eaux": "DDE",
    "incendie": "INCENDIE",
    "vol": "VOL",
    "bris de glace": "BDG",
    "catastrophe naturelle": "CATNAT",
}
TOUTES_GARANTIES = list(NATURES.values())


def generer_contrats(n: int) -> list[dict]:
    contrats = []
    for i in range(n):
        date_effet = fake.date_between(start_date="-3y", end_date="-2m")
        # Chaque contrat couvre un sous-ensemble aléatoire de garanties.
        garanties = random.sample(TOUTES_GARANTIES, k=random.randint(2, 4))
        contrats.append(
            {
                "num_police": f"P-{100000 + i}",
                "nom_assure": fake.name(),
                "date_effet": date_effet.isoformat(),
                "garanties": garanties,
                "plafond": random.choice([5000, 10000, 20000, 50000]),
                "franchise": random.choice([150, 300, 500]),
                "statut": random.choices(["actif", "résilié"], weights=[0.9, 0.1])[0],
            }
        )
    return contrats


def generer_sinistres(contrats: list[dict], n: int) -> list[dict]:
    sinistres = []
    for i in range(n):
        contrat = random.choice(contrats)
        nature = random.choice(list(NATURES.keys()))
        # La date du sinistre est postérieure à la date d'effet (cohérence !).
        debut = dt.date.fromisoformat(contrat["date_effet"])
        date_sinistre = fake.date_between(start_date=debut, end_date="today")
        sinistres.append(
            {
                "id_sinistre": f"S-{500000 + i}",
                "num_police": contrat["num_police"],
                "date_sinistre": date_sinistre.isoformat(),
                "nature": nature,
                "montant": random.randint(200, 30000),
                "tiers": fake.company() if random.random() < 0.5 else None,
                "description": fake.sentence(nb_words=12),
            }
        )
    return sinistres


def pdf_constat(sinistre: dict, contrat: dict, chemin: str) -> None:
    """Constat de sinistre en texte natif (lisible directement par Document AI)."""
    c = canvas.Canvas(chemin, pagesize=A4)
    y = 800
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, y, "CONSTAT DE SINISTRE")
    c.setFont("Helvetica", 11)
    lignes = [
        f"N° police : {contrat['num_police']}",
        f"Assuré : {contrat['nom_assure']}",
        f"N° sinistre : {sinistre['id_sinistre']}",
        f"Date du sinistre : {sinistre['date_sinistre']}",
        f"Nature : {sinistre['nature']}",
        f"Montant estimé : {sinistre['montant']} EUR",
        f"Tiers impliqué : {sinistre['tiers'] or 'aucun'}",
        f"Description : {sinistre['description']}",
    ]
    for ligne in lignes:
        y -= 28
        c.drawString(72, y, ligne)
    c.save()


def charger_bigquery(project: str, dataset: str, contrats: list, sinistres: list) -> None:
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    for table, rows in [("contrats", contrats), ("sinistres", sinistres)]:
        table_id = f"{project}.{dataset}.{table}"
        errors = client.insert_rows_json(table_id, rows)
        if errors:
            raise RuntimeError(f"Erreurs d'insertion sur {table}: {errors}")
        print(f"  {len(rows)} lignes insérées dans {table_id}")


def televerser_pdfs(project: str, bucket: str, dossier: str) -> None:
    from google.cloud import storage

    client = storage.Client(project=project)
    b = client.bucket(bucket)
    for nom in os.listdir(dossier):
        blob = b.blob(f"constats/{nom}")
        blob.upload_from_filename(os.path.join(dossier, nom))
    print(f"  PDF téléversés dans gs://{bucket}/constats/")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--dataset", default="assurance")
    p.add_argument("--bucket", help="Bucket des PDF. Omettre pour ne générer que les PDF en local.")
    p.add_argument("--nb-contrats", type=int, default=50)
    p.add_argument("--nb-sinistres", type=int, default=120)
    p.add_argument("--nb-pdf", type=int, default=10)
    p.add_argument("--load-bq", action="store_true", help="Charge dans BigQuery.")
    args = p.parse_args()

    print("Génération des données…")
    contrats = generer_contrats(args.nb_contrats)
    sinistres = generer_sinistres(contrats, args.nb_sinistres)

    par_police = {c["num_police"]: c for c in contrats}
    os.makedirs("pdfs", exist_ok=True)
    for s in sinistres[: args.nb_pdf]:
        pdf_constat(s, par_police[s["num_police"]], f"pdfs/{s['id_sinistre']}.pdf")
    print(f"  {args.nb_pdf} constats PDF générés dans ./pdfs/")

    if args.load_bq:
        charger_bigquery(args.project, args.dataset, contrats, sinistres)
    if args.bucket:
        televerser_pdfs(args.project, args.bucket, "pdfs")

    print("Terminé.")


if __name__ == "__main__":
    main()
