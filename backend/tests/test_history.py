from app.scoring_history import weighted_rates

def test_history_excludes_future_preseason_and_downweights_old_season():
    def row(day,year=2027,stype=2,score=120):
        return dict(start=day+'T00:00Z',season_year=year,season_type=stype,home_id='1',away_id='2',home_score=score,away_score=100)
    current=row('2026-10-23');old=row('2026-04-01',2026)
    f,a,meta=weighted_rates([current,old,row('2026-10-26',score=190),row('2026-10-22',stype=1,score=190)],'1','2026-10-24T00:00Z',2027,114,12)
    assert meta['games']==2 and 1<meta['effective_games']<1.3 and 114<f<120 and 100<a<114
    assert weighted_rates([],'1','2026-10-24T00:00Z',2027,114,12)[:2]==(114,114)
