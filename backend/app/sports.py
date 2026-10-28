"""League identities keep history, forecasts and settlement separate."""
from typing import Literal
SOCCER={
 'ucl':('Champions League','uefa.champions','CL'),
 'epl':('Premier League','eng.1','PL'),
 'laliga':('La Liga','esp.1','PD'),
 'ligue1':('Ligue 1','fra.1','FL1'),
 'bundesliga':('Bundesliga','ger.1','BL1'),
 'seriea':('Serie A','ita.1','SA'),
}
Sport=Literal['nhl','nba','nfl','ncaaf','ucl','epl','laliga','ligue1','bundesliga','seriea']
