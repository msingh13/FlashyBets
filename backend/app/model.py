"""NHL v1: independent regulation Poissons; one settlement goal on every tie."""
import math
from typing import Protocol

class SportsModel(Protocol):
    def predict(self, home_rate: float, away_rate: float, line: float, ot_home: float = .5) -> dict: ...

def decimal(american):
    if not american or abs(american) < 100:
        raise ValueError("American odds must be <= -100 or >= 100")
    return 1 + (american / 100 if american > 0 else 100 / abs(american))

def market(prob, push, odds):
    d = decimal(odds)
    return {"probability": prob, "push": push, "odds": odds,
            "implied": 1/d, "ev": prob*(d-1)-(1-prob-push)}

class NHLModel:
    def predict(self, home_rate, away_rate, line, ot_home=.5):
        if not (0 < home_rate <= 10 and 0 < away_rate <= 10 and 0 <= ot_home <= 1 and 0 <= line <= 30):
            raise ValueError("Invalid model inputs")
        # 60 goals gives negligible tail for supported lambda <= 10.
        def pmf(rate): return [math.exp(-rate)*rate**k/math.factorial(k) for k in range(61)]
        hp, ap = pmf(home_rate), pmf(away_rate)
        home=ties=over=under=push=total=0.
        distribution={}
        for h, ph in enumerate(hp):
            for a, pa in enumerate(ap):
                p=ph*pa
                ties += p if h==a else 0
                home += p*(ot_home if h==a else int(h>a))
                # NHL final score adds one goal in overtime or shootout.
                goals=h+a+int(h==a)
                distribution[goals]=distribution.get(goals,0)+p
                over += p if goals>line else 0
                under += p if goals<line else 0
                push += p if goals==line else 0
                total += goals*p
        return {"home":home,"away":1-home,"tie":ties,"over":over,"under":under,"push":push,
                "expected_total":total,"home_rate":home_rate,"away_rate":away_rate,
                "distribution":[{"goals":k,"probability":v} for k,v in sorted(distribution.items()) if k<=16],
                "version":"nhl-poisson-v1","ot_home":ot_home}
