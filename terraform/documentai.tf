# Processeur Document AI (Form Parser) créé automatiquement.
# Évite l'étape manuelle en console.
resource "google_document_ai_processor" "form_parser" {
  location     = "eu"
  display_name = "constat-parser"
  type         = "FORM_PARSER_PROCESSOR"

  depends_on = [google_project_service.enabled]
}
