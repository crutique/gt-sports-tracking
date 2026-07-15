"""Platform-name → scraper-module map."""
from pipeline.scrapers import fixture, mlbstats, scorebook

SCRAPERS = {"fixture": fixture, "mlbstats": mlbstats, "scorebook": scorebook}
