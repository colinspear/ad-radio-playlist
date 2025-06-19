import os
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

def test_is_token_expired_true(monkeypatch):
    monkeypatch.setattr(arp.requests, 'get', lambda url, headers, timeout: DummyResponse(status_code=401))
    assert arp.is_token_expired('token') is True

def test_is_token_expired_false(monkeypatch):
    monkeypatch.setattr(arp.requests, 'get', lambda url, headers, timeout: DummyResponse(status_code=200))
    assert arp.is_token_expired('token') is False

def test_refresh_tokens_success(monkeypatch):
    # Setup module-level credentials
    arp.REFRESH_TOKEN = 'old_refresh'
    arp.CLIENT_ID = 'cid'
    arp.CLIENT_SECRET = 'secret'
    # Mock requests.post to return new tokens
    def fake_post(url, data, headers, timeout):
        assert data['refresh_token'] == 'old_refresh'
        return DummyResponse(status_code=200, json_data={'access_token': 'new_access', 'refresh_token': 'new_refresh'})
    monkeypatch.setattr(arp.requests, 'post', fake_post)
    # Prevent actual .env writes
    monkeypatch.setattr(arp, 'set_key', lambda path, key, val: None)
    # Call and verify
    new_access = arp.refresh_tokens()
    assert new_access == 'new_access'

def test_search_track_success(monkeypatch):
    sample_uri = 'spotify:track:123'
    resp_data = {'tracks': {'items': [{'uri': sample_uri}]}}
    monkeypatch.setattr(arp.requests, 'get', lambda url, headers, params, timeout: DummyResponse(status_code=200, json_data=resp_data))
    uri = arp.search_track('Artist Song', headers={'Authorization': 'Bearer x'})
    assert uri == sample_uri

def test_search_track_not_found(monkeypatch):
    resp_data = {'tracks': {'items': []}}
    monkeypatch.setattr(arp.requests, 'get', lambda url, headers, params, timeout: DummyResponse(status_code=200, json_data=resp_data))
    with pytest.raises(ValueError):
        arp.search_track('Artist Song', headers={'Authorization': 'Bearer x'})

def test_get_latest_episode_url_success(monkeypatch):
    html = b'<html><h2 class="entry-title"><a href="http://example.com/episode">Episode</a></h2></html>'
    monkeypatch.setattr(arp.requests, 'get', lambda url, timeout: DummyResponse(status_code=200, content=html))
    url = arp.get_latest_episode_url()
    assert url == "http://example.com/episode"

def test_get_latest_episode_url_failure(monkeypatch):
    monkeypatch.setattr(arp.requests, 'get', lambda url, timeout: DummyResponse(status_code=404))
    with pytest.raises(RuntimeError):
        arp.get_latest_episode_url()

def test_get_artists_songs_success(monkeypatch):
    line = 'SIRIUS ++ Artist1 - Song1 ++ Artist2 - Song2'
    html = f'<div class="entry-content">{line}</div>'.encode()
    monkeypatch.setattr(arp.requests, 'get', lambda url, timeout: DummyResponse(status_code=200, content=html))
    songs = arp.get_artists_songs('http://example.com')
    assert songs == ['Artist1 - Song1', 'Artist2 - Song2']

def test_get_artists_songs_failure(monkeypatch):
    monkeypatch.setattr(arp.requests, 'get', lambda url, timeout: DummyResponse(status_code=200, content=b'<div></div>'))
    with pytest.raises(RuntimeError):
        arp.get_artists_songs('http://example.com')
