"""Platform-name → scraper-module map."""
from pipeline.scrapers import fixture, iscore, mlbstats, scorebook

SCRAPERS = {"fixture": fixture, "iscore": iscore, "mlbstats": mlbstats, "scorebook": scorebook}
