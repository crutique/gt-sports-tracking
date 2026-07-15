"""Platform-name → scraper-module map."""
from pipeline.scrapers import fixture, iscore, mlbstats, prestosports, scorebook

SCRAPERS = {"fixture": fixture, "iscore": iscore, "mlbstats": mlbstats,
            "prestosports": prestosports, "scorebook": scorebook}
