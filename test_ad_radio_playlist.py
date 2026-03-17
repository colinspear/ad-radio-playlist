import json
from datetime import datetime, timedelta, timezone

import pytest

import ad_radio_playlist as arp


class DummyResponse:
    def __init__(self, status_code=200, json_data=None, content=b""):
        self.status_code = status_code
        self._json = json_data or {}
        self.content = content

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise arp.requests.HTTPError(f"HTTP {self.status_code}")


# ---------------------------------------------------------------------------
# Spotify helpers
# ---------------------------------------------------------------------------

def test_search_track_success(monkeypatch):
    sample_uri = "spotify:track:123"
    resp_data = {"tracks": {"items": [{"uri": sample_uri}]}}
    monkeypatch.setattr(
        arp.requests, "get",
        lambda url, headers, params, timeout: DummyResponse(json_data=resp_data),
    )
    uri = arp.search_track("Artist Song", headers={"Authorization": "Bearer x"})
    assert uri == sample_uri


def test_search_track_not_found(monkeypatch):
    resp_data = {"tracks": {"items": []}}
    monkeypatch.setattr(
        arp.requests, "get",
        lambda url, headers, params, timeout: DummyResponse(json_data=resp_data),
    )
    with pytest.raises(ValueError):
        arp.search_track("Artist Song", headers={"Authorization": "Bearer x"})


# ---------------------------------------------------------------------------
# Show window calculation (DST-aware)
# ---------------------------------------------------------------------------

def test_get_show_window_pst():
    """January (PST): Wed 7–9 PM PST = Thu 03:00–05:00 UTC."""
    # Thu Jan 16 2025 10:00 UTC — show ended hours ago
    ref = datetime(2025, 1, 16, 10, 0, tzinfo=timezone.utc)
    start, end = arp.get_show_window(ref)
    assert start == datetime(2025, 1, 16, 3, 0, tzinfo=timezone.utc)
    assert end == datetime(2025, 1, 16, 5, 0, tzinfo=timezone.utc)


def test_get_show_window_pdt():
    """March after DST (PDT): Wed 7–9 PM PDT = Thu 02:00–04:00 UTC."""
    # Thu Mar 20 2025 10:00 UTC — DST started March 9
    ref = datetime(2025, 3, 20, 10, 0, tzinfo=timezone.utc)
    start, end = arp.get_show_window(ref)
    assert start == datetime(2025, 3, 20, 2, 0, tzinfo=timezone.utc)
    assert end == datetime(2025, 3, 20, 4, 0, tzinfo=timezone.utc)


def test_get_show_window_before_show():
    """Wednesday afternoon in LA — show hasn't happened yet, return last week."""
    # Wed Mar 19 2025 18:00 UTC = Wed 11 AM PDT, show not started
    ref = datetime(2025, 3, 19, 18, 0, tzinfo=timezone.utc)
    start, end = arp.get_show_window(ref)
    # Previous week: Wed Mar 12 7–9 PM PDT = Thu Mar 13 02:00–04:00 UTC
    assert start == datetime(2025, 3, 13, 2, 0, tzinfo=timezone.utc)
    assert end == datetime(2025, 3, 13, 4, 0, tzinfo=timezone.utc)


def test_get_show_window_saturday():
    """Saturday — should return the most recent Wednesday's show."""
    # Sat Mar 22 2025 12:00 UTC
    ref = datetime(2025, 3, 22, 12, 0, tzinfo=timezone.utc)
    start, end = arp.get_show_window(ref)
    # Wed Mar 19 7–9 PM PDT = Thu Mar 20 02:00–04:00 UTC
    assert start == datetime(2025, 3, 20, 2, 0, tzinfo=timezone.utc)
    assert end == datetime(2025, 3, 20, 4, 0, tzinfo=timezone.utc)


def test_get_show_window_during_show():
    """During the show — should return last week since this one hasn't ended."""
    # Thu Mar 20 2025 03:00 UTC = Wed 8 PM PDT (mid-show)
    ref = datetime(2025, 3, 20, 3, 0, tzinfo=timezone.utc)
    start, end = arp.get_show_window(ref)
    # Previous week
    assert start == datetime(2025, 3, 13, 2, 0, tzinfo=timezone.utc)
    assert end == datetime(2025, 3, 13, 4, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# xmplaylist fetch
# ---------------------------------------------------------------------------

def _make_xm_entry(title, artists, spotify_id, timestamp_str):
    entry = {
        "id": f"id-{title}",
        "timestamp": timestamp_str,
        "track": {"id": f"t-{title}", "title": title, "artists": artists},
    }
    if spotify_id:
        entry["spotify"] = {"id": spotify_id}
    return entry


def test_fetch_xmplaylist_tracks_filters_by_window(monkeypatch):
    """Only tracks within the window should be returned."""
    start = datetime(2025, 3, 20, 2, 0, tzinfo=timezone.utc)
    end = datetime(2025, 3, 20, 4, 0, tzinfo=timezone.utc)

    entries = [
        _make_xm_entry("In Window", ["Artist A"], "sp1", "2025-03-20T03:00:00Z"),
        _make_xm_entry("Too Early", ["Artist B"], "sp2", "2025-03-20T01:30:00Z"),
        _make_xm_entry("Also In", ["Artist C"], "sp3", "2025-03-20T02:30:00Z"),
    ]

    def fake_get(url, headers, params, timeout):
        return DummyResponse(json_data={"results": entries, "next": None})

    monkeypatch.setattr(arp.requests, "get", fake_get)

    tracks = arp.fetch_xmplaylist_tracks(start, end)
    assert len(tracks) == 2
    # Should be chronological
    assert tracks[0]["title"] == "Also In"
    assert tracks[1]["title"] == "In Window"


def test_fetch_xmplaylist_tracks_empty_results(monkeypatch):
    start = datetime(2025, 3, 20, 2, 0, tzinfo=timezone.utc)
    end = datetime(2025, 3, 20, 4, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        arp.requests, "get",
        lambda url, headers, params, timeout: DummyResponse(json_data={"results": []}),
    )
    tracks = arp.fetch_xmplaylist_tracks(start, end)
    assert tracks == []


def test_fetch_xmplaylist_tracks_no_spotify_id(monkeypatch):
    """Tracks without spotify data should still be collected."""
    start = datetime(2025, 3, 20, 2, 0, tzinfo=timezone.utc)
    end = datetime(2025, 3, 20, 4, 0, tzinfo=timezone.utc)

    entries = [
        _make_xm_entry("No Spotify", ["Artist X"], None, "2025-03-20T02:15:00Z"),
    ]

    monkeypatch.setattr(
        arp.requests, "get",
        lambda url, headers, params, timeout: DummyResponse(
            json_data={"results": entries, "next": None}
        ),
    )
    tracks = arp.fetch_xmplaylist_tracks(start, end)
    assert len(tracks) == 1
    assert tracks[0]["spotify_id"] is None


# ---------------------------------------------------------------------------
# URI resolution
# ---------------------------------------------------------------------------

def test_tracks_to_spotify_uris_direct_id(monkeypatch):
    """Tracks with a spotify_id should produce a URI without searching."""
    tracks = [
        {"title": "Song", "artists": ["Artist"], "spotify_id": "abc123", "timestamp": None},
    ]
    uris, skipped = arp.tracks_to_spotify_uris(tracks, {"Authorization": "Bearer x"})
    assert uris == ["spotify:track:abc123"]
    assert skipped == []


def test_tracks_to_spotify_uris_fallback_search(monkeypatch):
    """Tracks without spotify_id should fall back to search."""
    tracks = [
        {"title": "Song", "artists": ["Artist"], "spotify_id": None, "timestamp": None},
    ]

    def fake_get(url, headers, params, timeout):
        return DummyResponse(
            json_data={"tracks": {"items": [{"uri": "spotify:track:found"}]}}
        )

    monkeypatch.setattr(arp.requests, "get", fake_get)
    uris, skipped = arp.tracks_to_spotify_uris(tracks, {"Authorization": "Bearer x"})
    assert uris == ["spotify:track:found"]
    assert skipped == []


def test_tracks_to_spotify_uris_search_fails(monkeypatch):
    """Tracks that can't be found via search should be skipped."""
    tracks = [
        {"title": "Obscure", "artists": ["Nobody"], "spotify_id": None, "timestamp": None},
    ]

    def fake_get(url, headers, params, timeout):
        return DummyResponse(json_data={"tracks": {"items": []}})

    monkeypatch.setattr(arp.requests, "get", fake_get)
    uris, skipped = arp.tracks_to_spotify_uris(tracks, {"Authorization": "Bearer x"})
    assert uris == []
    assert len(skipped) == 1
