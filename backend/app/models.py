"""Separate, deliberately uncalibrated scoring baselines for each sport."""
import math
from .model import NHLModel

def cdf(x, mean, sd):
    return .5*(1+math.erf((x-mean)/(sd*math.sqrt(2))))

class NBAModel:
    def predict(self, home_rate, away_rate, line, ot_home=.5):
        if not all(math.isfinite(x) for x in [home_rate,away_rate,line]) or not (0<home_rate<200 and 0<away_rate<200 and 0<=line<=400):
            raise ValueError('Invalid NBA inputs')
        # Final-score margin/total model, fitted to final-score inputs including OT.
        # sd values are explicit starting assumptions, not fitted estimates.
        mean=home_rate+away_rate
        home=1-cdf(0,home_rate-away_rate,15)
        if float(line).is_integer():
            under=cdf(line-.5,mean,20);over=1-cdf(line+.5,mean,20)
        else:
            under=cdf(line,mean,20);over=1-under
        return {'home':home,'away':1-home,'tie':0,'ml_push':0,'over':over,'under':under,
            'push':max(0,1-over-under),'expected_total':mean,'home_rate':home_rate,'away_rate':away_rate,
            'distribution':[],'version':'nba-final-gaussian-v1','assumptions':'Final-score Gaussian margin σ=15, total σ=20; includes OT in historical scores, no NBA final tie.'}

class NFLModel:
    def predict(self, home_rate, away_rate, line, ot_home=.5):
        if not all(math.isfinite(x) for x in [home_rate,away_rate,line]) or not (0<home_rate<=50 and 0<away_rate<=50 and 0<=line<=120):
            raise ValueError('Invalid NFL inputs')
        # Eleven possessions, each 0/3/7 points. This is an illustrative drive model.
        def scores(mean):
            scoring=mean/(11*(.68*7+.32*3));dist={0:1.}
            for _ in range(11):
                nxt={}
                for score,p in dist.items():
                    for points,q in [(0,1-scoring),(3,scoring*.32),(7,scoring*.68)]:
                        nxt[score+points]=nxt.get(score+points,0)+p*q
                dist=nxt
            return dist
        hd,ad=scores(home_rate),scores(away_rate)
        home=away=tie=expected=over=under=push=0.;totals={}
        for h,ph in hd.items():
            for a,pa in ad.items():
                p=ph*pa
                if h>a: home+=p
                elif a>h: away+=p
                else:
                    # Conditional tie survival 10%; the rest split equally.
                    home+=p*.45;away+=p*.45;tie+=p*.1
                endings=[(0,1.)] if h!=a else [(0,.1),(3,.9*.32),(7,.9*.68)]
                for extra,q in endings:
                    total=h+a+extra;mass=p*q
                    totals[total]=totals.get(total,0)+mass
                    expected+=total*mass
                    over+=mass if total>line else 0
                    under+=mass if total<line else 0
                    push+=mass if total==line else 0
        return {'home':home,'away':away,'tie':tie,'ml_push':tie,'over':over,'under':under,'push':push,
            'expected_total':expected,'home_rate':home_rate,'away_rate':away_rate,
            'distribution':[{'goals':k,'probability':v} for k,v in sorted(totals.items())],
            'version':'nfl-drive-v1','assumptions':'11 possessions; scoring outcomes 3/7 points with fixed 32/68% mix. Tied regulation: 10% remain tied; 90% receive one 3/7-point settlement score. Regular season only; 2-way ML tie returns stake. Uncalibrated approximation, not a complete NFL OT simulation.'}

from .soccer import SoccerModel

MODELS={'ucl':SoccerModel(),'nhl':NHLModel(),'nba':NBAModel(),'nfl':NFLModel()}
