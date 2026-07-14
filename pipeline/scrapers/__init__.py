"""Platform-name → scraper-module map. Real platforms register here in Plan 3."""
from pipeline.scrapers import fixture

SCRAPERS = {"fixture": fixture}
