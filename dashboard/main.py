"""Dashboard de suivi des dossiers sinistres.
Lit suivi_dossiers dans BigQuery et expose une interface web.
"""
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from google.cloud import bigquery

app = FastAPI(title="Dashboard sinistres")
_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
_DATASET = os.environ.get("BQ_DATASET", "assurance")
_BUCKET  = os.environ.get("BUCKET_SINISTRES", "")


def _bq():
    return bigquery.Client(project=_PROJECT)


def _get_dossiers():
    """Récupère le dernier statut de chaque dossier."""
    query = f"""
        SELECT
            id_sinistre,
            ARRAY_AGG(statut ORDER BY horodatage DESC LIMIT 1)[OFFSET(0)] AS statut,
            ARRAY_AGG(etape   ORDER BY horodatage DESC LIMIT 1)[OFFSET(0)] AS etape,
            ARRAY_AGG(detail  ORDER BY horodatage DESC LIMIT 1)[OFFSET(0)] AS detail,
            MAX(horodatage) AS derniere_maj,
            MIN(horodatage) AS premiere_maj,
            COUNT(*) AS nb_etapes
        FROM `{_PROJECT}.{_DATASET}.suivi_dossiers`
        GROUP BY id_sinistre
        ORDER BY derniere_maj DESC
        LIMIT 50
    """
    rows = list(_bq().query(query).result())
    return [dict(r) for r in rows]


def _progression(statut):
    return {"reçu": 25, "extrait": 50, "instruit": 75, "décidé": 100, "erreur": 25}.get(statut, 0)


def _badge(statut):
    cls = {"reçu": "recv", "extrait": "extr", "instruit": "inst",
           "décidé": "deci", "erreur": "err"}.get(statut, "recv")
    icon = {"décidé": "✓", "erreur": "✗"}.get(statut, "·")
    return f'<span class="badge b-{cls}">{icon} {statut.capitalize()}</span>'


def _kpis(dossiers):
    total  = len(dossiers)
    decid  = sum(1 for d in dossiers if d["statut"] == "décidé")
    cours  = sum(1 for d in dossiers if d["statut"] in ("reçu","extrait","instruit"))
    errors = sum(1 for d in dossiers if d["statut"] == "erreur")
    return total, decid, cours, errors


@app.get("/", response_class=HTMLResponse)
def index():
    dossiers = _get_dossiers()
    total, decid, cours, errors = _kpis(dossiers)

    lignes = ""
    for d in dossiers:
        prog   = _progression(d["statut"])
        badge  = _badge(d["statut"])
        maj    = str(d["derniere_maj"])[:16].replace("T", " ")
        detail = d.get("detail") or ""
        pdf_btn = ""
        if d["statut"] == "décidé" and _BUCKET:
            uri = f"gs://{_BUCKET}/decisions/decision-{d['id_sinistre']}.pdf"
            pdf_btn = f'<span class="id muted" title="{uri}">📄 PDF prêt</span>'
        elif d["statut"] == "erreur":
            pdf_btn = f'<span class="badge b-err" title="{detail}">✗ Erreur</span>'
        col_prog = (
            f'<div class="prog"><div class="prog-fill'
            f'{"--err" if d["statut"]=="erreur" else ""}" '
            f'style="width:{prog}%"></div></div>'
            f'<span class="prog-lbl">{prog}%</span>'
        )
        lignes += f"""<tr>
          <td><span class="id">{d['id_sinistre']}</span></td>
          <td>{badge}</td>
          <td>{col_prog}</td>
          <td class="muted">{maj}</td>
          <td>{pdf_btn}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8">
<meta http-equiv="refresh" content="30">
<title>Suivi sinistres</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#0F1524;color:#E6ECF7;min-height:100vh;padding:0}}
  header{{background:#161E30;border-bottom:1px solid #26314A;padding:18px 32px;display:flex;align-items:center;justify-content:space-between}}
  .logo{{font-size:18px;font-weight:700;color:#fff}}.logo span{{color:#2EC4B6}}
  .refresh{{font-size:12px;color:#8A97B2}}
  main{{padding:28px 32px;max-width:1200px;margin:0 auto}}
  .kpi-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px}}
  .kpi{{background:#161E30;border:1px solid #26314A;border-radius:12px;padding:20px 24px}}
  .kpi-val{{font-size:36px;font-weight:700;color:#fff}}
  .kpi-lab{{font-size:13px;color:#8A97B2;margin-top:4px}}
  .kpi.ok .kpi-val{{color:#2EC4B6}}.kpi.warn .kpi-val{{color:#F4B740}}.kpi.err .kpi-val{{color:#E24B4A}}
  .card{{background:#161E30;border:1px solid #26314A;border-radius:12px;overflow:hidden}}
  .card-head{{padding:16px 24px;border-bottom:1px solid #26314A;font-size:15px;font-weight:600;color:#fff}}
  table{{width:100%;border-collapse:collapse}}
  th{{padding:10px 20px;text-align:left;font-size:12px;color:#8A97B2;font-weight:600;letter-spacing:.5px;background:#0F1524}}
  td{{padding:14px 20px;border-top:1px solid #1a2235;font-size:14px}}
  tr:hover td{{background:#1a2235}}
  .id{{font-family:'Consolas',monospace;font-size:13px;color:#CADCFC}}
  .muted{{color:#8A97B2;font-size:13px}}
  .badge{{display:inline-flex;align-items:center;gap:5px;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600}}
  .b-recv{{background:rgba(46,196,182,.15);color:#2EC4B6}}
  .b-extr{{background:rgba(244,183,64,.15);color:#F4B740}}
  .b-inst{{background:rgba(53,130,220,.15);color:#5B8FD4}}
  .b-deci{{background:rgba(46,196,182,.2);color:#2EC4B6;border:1px solid rgba(46,196,182,.3)}}
  .b-err{{background:rgba(226,75,74,.15);color:#E24B4A}}
  .prog{{height:6px;background:#26314A;border-radius:3px;width:120px;overflow:hidden;display:inline-block;vertical-align:middle}}
  .prog-fill{{height:100%;background:#2EC4B6;border-radius:3px;transition:width .3s}}
  .prog-fill--err{{background:#E24B4A}}
  .prog-lbl{{font-size:12px;color:#8A97B2;margin-left:8px;vertical-align:middle}}
  footer{{text-align:center;padding:20px;color:#5A6378;font-size:12px}}
</style></head><body>
<header>
  <span class="logo">Agent <span>Sinistres</span> · Suivi</span>
  <span class="refresh">⟳ Actualisation automatique toutes les 30 s</span>
</header>
<main>
  <div class="kpi-row">
    <div class="kpi"><div class="kpi-val">{total}</div><div class="kpi-lab">Dossiers suivis</div></div>
    <div class="kpi ok"><div class="kpi-val">{decid}</div><div class="kpi-lab">Décidés</div></div>
    <div class="kpi warn"><div class="kpi-val">{cours}</div><div class="kpi-lab">En cours</div></div>
    <div class="kpi err"><div class="kpi-val">{errors}</div><div class="kpi-lab">En erreur</div></div>
  </div>
  <div class="card">
    <div class="card-head">Dossiers récents</div>
    <table>
      <thead><tr>
        <th>DOSSIER</th><th>STATUT</th><th>PROGRESSION</th>
        <th>DERNIÈRE MAJ</th><th>DÉCISION</th>
      </tr></thead>
      <tbody>{lignes}</tbody>
    </table>
  </div>
</main>
<footer>Agent Sinistres · GCP · {_PROJECT}</footer>
</body></html>"""
    return html


@app.get("/api/dossiers")
def api_dossiers():
    """Endpoint JSON pour les intégrations futures."""
    return _get_dossiers()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
