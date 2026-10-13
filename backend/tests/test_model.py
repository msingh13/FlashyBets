import pytest
from app.model import NHLModel,market,decimal
from app.history import evaluate

def test_symmetry_and_mass():
    p=NHLModel().predict(3,3,6)
    assert p['home']==pytest.approx(.5)
    assert p['over']+p['under']+p['push']==pytest.approx(1)
    assert p['expected_total']==pytest.approx(6+p['tie'])

def test_ot_changes_moneyline_not_total():
    a=NHLModel().predict(3,2,5.5,0);b=NHLModel().predict(3,2,5.5,1)
    assert b['home']-a['home']==pytest.approx(a['tie'])
    assert a['over']==b['over']

def test_integer_settlement_ties_never_even():
    p=NHLModel().predict(3,3,6)
    assert p['push']>0
    assert sum(x['probability'] for x in p['distribution'])>.999

def test_ev_push_and_odds():
    assert decimal(-110)==pytest.approx(1+100/110)
    assert market(.4,.2,100)['ev']==pytest.approx(0)
    with pytest.raises(ValueError): decimal(0)

def test_leakage_guard():
    with pytest.raises(ValueError): evaluate([{'start':'2025-01-01','feature_asof':'2025-01-02','odds_asof':'2024-01-01'}])

def test_invalid_rates():
    with pytest.raises(ValueError): NHLModel().predict(-1,3,6.5)

def test_timezone_comparison():
    from app.history import timestamp
    assert timestamp('2025-01-01T20:00:00-05:00') > timestamp('2025-01-02T00:00:00Z')
    with pytest.raises(ValueError): timestamp('2025-01-01')
