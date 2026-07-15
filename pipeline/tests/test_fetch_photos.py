from pipeline import fetch_photos

PLAYERS = [
    {"slug": "a", "summer": {"status": "assigned", "league": "nw", "stats_id": "123"}},
    {"slug": "b", "summer": {"status": "assigned", "league": "nw", "stats_id": "not-numeric"}},
    {"slug": "c", "summer": {"status": "assigned", "league": "other", "stats_id": "9"}},
    {"slug": "d", "summer": {"status": "unassigned"}},
]
LEAGUES = {"nw": {"platform": "scorebook", "api_base": "https://x/api"},
           "other": {"platform": "pending"}}


def test_photo_targets_filters_to_scorebook_numeric_ids():
    targets = fetch_photos.photo_targets(PLAYERS, LEAGUES)
    assert targets == [("a", "https://x/api/player/123")]
