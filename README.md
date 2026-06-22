# Agent Sinistres — projet GCP (Terraform + CI/CD)

Un agent IA qui instruit un dossier de sinistre d'assurance : il récupère le
contrat et le sinistre, vérifie l'éligibilité, cite les conditions générales,
détecte les anomalies, puis rédige une décision. Infra 100 % Terraform,
déploiement continu sans clé via GitHub Actions + Workload Identity Federation.

## Architecture

```
Dépôt PDF (Cloud Storage) -> Document AI (extraction) -> table sinistres (BigQuery)
                                                               |
   Requête API -> Cloud Run -> Agent Gemini --(outils)--> BigQuery (contrats/sinistres)
                                            \-> règles métier (éligibilité, anomalies)
```

## Arborescence

| Dossier | Rôle |
|---|---|
| `terraform/` | toute l'infra GCP (BigQuery, Storage, Cloud Run, IAM, WIF) |
| `data_generation/` | Faker + reportlab : tables + PDF synthétiques |
| `ingest/` | lecture des PDF via Document AI |
| `agent/` | l'agent (google-genai), l'API FastAPI, le Dockerfile |
| `tests/` | tests des règles métier (sans GCP) |
| `.github/workflows/` | CI (lint + tests) et Deploy (build + Cloud Run) |

---

## Prérequis (Windows, sans accès admin)

Le plus simple : **fais tout depuis Google Cloud Shell**
(https://shell.cloud.google.com). C'est un terminal Linux dans le navigateur
avec `gcloud`, `terraform`, `python`, `git` déjà installés et authentifiés —
**aucune installation locale, aucun admin requis**.

Si tu préfères travailler en local sous Windows :
- gcloud CLI : installeur « for current user only » (sans admin).
- Python : `winget install Python.Python.3.12 --scope user`, puis un venv :
  `python -m venv .venv` puis `.venv\Scripts\activate`.
- Terraform : télécharge le binaire, place-le dans un dossier de ton `PATH`
  utilisateur (ex. `%USERPROFILE%\bin`). Pas d'admin.

Toutes les commandes ci-dessous tiennent **sur une seule ligne** : elles
fonctionnent à l'identique dans `cmd`, PowerShell et Cloud Shell.

---

## Étape 1 — Projet GCP et facturation

```
gcloud auth login
gcloud projects create mon-projet-assurance --name="Agent Sinistres"
gcloud config set project mon-projet-assurance
```

Active la facturation sur le projet (obligatoire pour Vertex AI / Gemini) :
console > Facturation, ou
`gcloud billing projects link mon-projet-assurance --billing-account=XXXXXX-XXXXXX-XXXXXX`.
Le crédit gratuit de 300 $ couvre largement ce projet.

## Étape 2 — Récupérer le code sur GitHub

Crée un dépôt GitHub vide `ton-compte/agent-sinistres`, puis :

```
git init && git add . && git commit -m "init"
git branch -M main
git remote add origin https://github.com/ton-compte/agent-sinistres.git
git push -u origin main
```

(Le push échouera côté CI tant que les secrets ne sont pas créés — c'est normal,
on les ajoute à l'étape 6.)

## Étape 3 — Bucket pour le state Terraform

Le state Terraform doit vivre ailleurs que sur ta machine :

```
gcloud storage buckets create gs://mon-projet-assurance-tfstate --location=europe-west1
```

Puis dans `terraform/versions.tf`, dé-commente le bloc `backend "gcs"` et mets
ton bucket.

## Étape 4 — Déployer l'infra avec Terraform

```
cd terraform
copy terraform.tfvars.example terraform.tfvars
```

Édite `terraform.tfvars` : ton `project_id` et ton `github_repo`
(`ton-compte/agent-sinistres`). Puis :

```
terraform init
terraform apply
```

Terraform crée : les APIs, BigQuery (`contrats`, `sinistres`), le bucket des
sinistres, Artifact Registry, les comptes de service, la fédération WIF et un
service Cloud Run (avec une image « hello » provisoire). Note les sorties :
`workload_identity_provider`, `deployer_service_account`, `cloud_run_url`.

## Étape 5 — Générer les données et tester Document AI

Depuis Cloud Shell (ou ton venv) :

```
cd ../data_generation
pip install -r requirements.txt
python generate_data.py --project mon-projet-assurance --bucket mon-projet-assurance-sinistres --load-bq
```

Ça remplit BigQuery et téléverse 10 constats PDF.

Le processeur Document AI est **déjà créé par Terraform** (sortie
`documentai_processor_id`). Pour vérifier l'extraction sur un PDF local :

```
cd ../ingest
pip install -r requirements.txt
python process_document.py --project mon-projet-assurance --processor TON_PROCESSOR_ID --file ../data_generation/pdfs/S-500000.pdf
```

Tu dois retrouver le numéro de police, la date et le montant que tu avais
écrits dans le PDF : la chaîne fonctionne.

## Étape 6 — Brancher le CI/CD (secrets GitHub)

Dans GitHub > Settings > Secrets and variables > Actions, crée 3 secrets avec
les sorties de Terraform :

| Secret | Valeur |
|---|---|
| `GCP_PROJECT_ID` | `mon-projet-assurance` |
| `WIF_PROVIDER` | sortie `workload_identity_provider` |
| `WIF_SERVICE_ACCOUNT` | sortie `deployer_service_account` |
| `DOCAI_PROCESSOR_ID` | sortie `documentai_processor_id` |

Aucune clé JSON n'est stockée : GitHub s'authentifie par jeton court (OIDC).

## Étape 7 — Déclencher le pipeline

```
git commit --allow-empty -m "ci: premier déploiement"
git push
```

- Le workflow **CI** lance le lint et les tests métier.
- Le workflow **Deploy** construit l'image, la pousse sur Artifact Registry et
  déploie sur Cloud Run.

## Étape 8 — Interroger l'agent

```
curl -X POST CLOUD_RUN_URL/instruire -H "Content-Type: application/json" -d "{\"num_police\": \"P-100001\", \"id_sinistre\": \"S-500000\"}"
```

L'agent renvoie sa décision : couverture, montant remboursable, clauses citées,
points de vigilance.

## Étape 9 — Ingestion automatique (le déclencheur)

Plus besoin de lancer un script à la main : dès qu'un PDF arrive dans le bucket,
Eventarc appelle le service `ingest-sinistres`, qui lit le document via
Document AI et insère le sinistre dans BigQuery. Pour le tester :

```
gcloud storage cp data_generation/pdfs/S-500000.pdf gs://mon-projet-assurance-sinistres/constats/
```

Au bout de quelques secondes, vérifie que la ligne est apparue :

```
bq query --use_legacy_sql=false "SELECT * FROM assurance.sinistres WHERE id_sinistre='S-500000'"
```

Tu peux suivre l'exécution dans les logs du service `ingest-sinistres`
(console > Cloud Run > ingest-sinistres > Logs). C'est le pipeline complet :
**dépôt PDF -> Document AI -> BigQuery**, sans aucune intervention manuelle.

---

## Tester en local avant de pousser

```
cd agent
pip install -r requirements.txt
set GOOGLE_CLOUD_PROJECT=mon-projet-assurance
python agent.py P-100001 S-500000
```

Les tests des règles (sans GCP) :

```
pip install pytest
set PYTHONPATH=agent
pytest tests/ -v
```

## Pour aller plus loin

- Remplacer `search_conditions` (base en dur) par **Vertex AI Search** pour un
  vrai RAG sur tes conditions générales.
- Restreindre l'accès Cloud Run (retirer `--allow-unauthenticated`).
- Ajouter un `terraform plan` automatique sur les pull requests.
- Convertir les PDF en images pour tester l'OCR sur du « scanné ».

## Coûts

À l'usage : Gemini (par requête), Document AI (par page), BigQuery (par requête,
généreux palier gratuit), Cloud Run (à la requête, palier gratuit). Pour un
projet d'apprentissage, le crédit de 300 $ suffit très largement.
