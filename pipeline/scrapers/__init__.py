"""Platform-name → scraper-module map."""
from pipeline.scrapers import fixture, scorebook

SCRAPERS = {"fixture": fixture, "scorebook": scorebook}
