"""Platform-name → scraper-module map."""
from pipeline.scrapers import fixture, mlbstats, prestosports, scorebook

SCRAPERS = {"fixture": fixture, "mlbstats": mlbstats,
            "prestosports": prestosports, "scorebook": scorebook}
