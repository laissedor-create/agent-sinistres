"""L'agent : un Gemini outillé qui instruit un dossier de sinistre.

Utilise le SDK google-genai (le nouveau, l'ancien vertexai.generative_models
étant retiré en juin 2026) avec l'appel de fonctions automatique : on passe
les fonctions Python comme outils, et le SDK gère la boucle d'appels.
"""
from __future__ import annotations

import os

import tools
from google import genai
from google.genai import types

_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "europe-west1")
_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")

SYSTEM = """Tu es un assistant d'instruction de sinistres d'assurance (IARD).
Méthode imposée, dans l'ordre :
1. Récupère le contrat avec get_contrat.
2. Récupère le sinistre avec get_sinistre.
3. Vérifie l'éligibilité avec check_eligibilite.
4. Recherche les clauses pertinentes avec search_conditions.
5. Repère les anomalies avec detect_anomalie.
Tu ne calcules JAMAIS un remboursement toi-même : tu utilises uniquement les
résultats des outils. Si un signal d'anomalie est présent, tu recommandes une
vérification manuelle plutôt qu'un accord automatique.
Conclus par : la décision, le montant remboursable, les clauses citées, et les
points de vigilance. Réponds en français, de façon concise et structurée."""

_TOOLS = [
    tools.get_contrat,
    tools.get_sinistre,
    tools.check_eligibilite,
    tools.search_conditions,
    tools.detect_anomalie,
]


def _client() -> genai.Client:
    return genai.Client(vertexai=True, project=_PROJECT, location=_LOCATION)


def instruire(num_police: str, id_sinistre: str) -> str:
    """Instruit un dossier et renvoie la décision rédigée."""
    client = _client()
    prompt = (
        f"Instruis le dossier : police {num_police}, sinistre {id_sinistre}. "
        "Suis la méthode imposée et conclus par une recommandation."
    )
    response = client.models.generate_content(
        model=_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            tools=_TOOLS,            # appel de fonctions automatique
            temperature=0.2,
        ),
    )
    return response.text


if __name__ == "__main__":
    import sys

    police = sys.argv[1] if len(sys.argv) > 1 else "P-100001"
    sinistre = sys.argv[2] if len(sys.argv) > 2 else "S-500000"
    print(instruire(police, sinistre))
