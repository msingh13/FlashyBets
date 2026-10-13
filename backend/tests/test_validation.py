from app import validation,store

def test_empty_evidence_is_not_accuracy(tmp_path):
    r=validation.report('ucl','live',str(tmp_path/'m.db'))
    assert r['recorded']==0 and r['status']=='Collecting prospective evidence'
    assert r['benchmarks']['ml']['model_brier'] is None

def test_same_game_neutral_benchmark(monkeypatch):
    monkeypatch.setattr(store,'ledger',lambda *a:{'forecasts':[{'start':'2026-10-01T19:00Z','captured':'2026-10-01T17:00Z','result':{},'markets':[]}]})
    # Empty result is pending, not a scored game.
    assert validation.report('nhl','live')['pending']==1
    monkeypatch.setattr(store,'ledger',lambda *a:{'forecasts':[{'start':'2026-10-01T19:00Z','captured':'2026-10-01T17:00Z','result':{'home_score':2,'away_score':1},'markets':[{'name':n,'probability':p,'outcome':o} for n,p,o in [('home',.8,'win'),('away',.2,'loss'),('over',.6,'loss'),('under',.4,'win')]]}]})
    r=validation.report('nhl','live');assert abs(r['benchmarks']['ml']['model_brier']-.08)<1e-8
    assert r['benchmarks']['ml']['baseline_brier']==.5 and r['settled_dates']==1
