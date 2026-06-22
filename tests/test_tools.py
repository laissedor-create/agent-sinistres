"""Tests des règles métier pures : aucun accès GCP requis, idéal pour la CI."""
import tools


def test_eligibilite_couvert():
    r = tools.check_eligibilite(
        nature="dégât des eaux", montant=2000, garanties=["DDE", "VOL"],
        plafond=10000, franchise=300,
    )
    assert r["couvert"] is True
    assert r["remboursement"] == 1700  # 2000 - 300


def test_eligibilite_plafonne():
    r = tools.check_eligibilite(
        nature="incendie", montant=50000, garanties=["INCENDIE"],
        plafond=10000, franchise=500,
    )
    assert r["remboursement"] == 10000  # plafonné


def test_eligibilite_garantie_absente():
    r = tools.check_eligibilite(
        nature="vol", montant=1000, garanties=["DDE"], plafond=10000, franchise=300,
    )
    assert r["couvert"] is False


def test_eligibilite_sous_franchise():
    r = tools.check_eligibilite(
        nature="bris de glace", montant=100, garanties=["BDG"],
        plafond=10000, franchise=300,
    )
    assert r["couvert"] is True
    assert r["remboursement"] == 0.0


def test_anomalie_sinistre_avant_contrat():
    r = tools.detect_anomalie(
        date_effet="2024-06-01", date_sinistre="2024-05-01", montant=1000, plafond=10000,
    )
    assert r["suspect"] is True


def test_anomalie_juste_apres_souscription():
    r = tools.detect_anomalie(
        date_effet="2024-06-01", date_sinistre="2024-06-10", montant=1000, plafond=10000,
    )
    assert r["suspect"] is True


def test_pas_d_anomalie():
    r = tools.detect_anomalie(
        date_effet="2023-01-01", date_sinistre="2024-06-10", montant=1000, plafond=10000,
    )
    assert r["suspect"] is False


def test_search_conditions_retourne_extraits():
    r = tools.search_conditions("le vol est-il couvert ?")
    assert len(r["extraits"]) >= 1
