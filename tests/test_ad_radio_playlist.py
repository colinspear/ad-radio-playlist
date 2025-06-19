import sys
import types
# Stub missing dependencies for testing environment
try:
    import dotenv
except ImportError:
    sys.modules['dotenv'] = types.SimpleNamespace(load_dotenv=lambda: None)
try:
    import requests
except ImportError:
    class HTTPError(Exception): pass
    def dummy_raise_for_status(): pass
    def dummy_json(): return {}
    dummy_resp = types.SimpleNamespace(status_code=200, text="", json=dummy_json, raise_for_status=dummy_raise_for_status)
    sys.modules['requests'] = types.SimpleNamespace(
        HTTPError=HTTPError,
        get=lambda *args, **kwargs: dummy_resp,
        post=lambda *args, **kwargs: dummy_resp,
        put=lambda *args, **kwargs: dummy_resp,
    )
try:
    import fastapi
except ImportError:
    class FastAPI:
        def get(self, path):
            def decorator(func): return func
            return decorator
    class HTTPException(Exception):
        def __init__(self, status_code, detail=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail
    sys.modules['fastapi'] = types.SimpleNamespace(
        FastAPI=FastAPI,
        HTTPException=HTTPException,
    )
try:
    import fastapi.responses
except ImportError:
    sys.modules['fastapi.responses'] = types.SimpleNamespace(HTMLResponse=lambda content=None: None)
try:
    import bs4
except ImportError:
    sys.modules['bs4'] = types.SimpleNamespace(
        BeautifulSoup=lambda *args, **kwargs: types.SimpleNamespace(find_all=lambda *a, **k: []),
    )
import os
import runpy
import unittest
from unittest.mock import patch


class TestEnvValidation(unittest.TestCase):
    def setUp(self):
        self._orig_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_missing_env(self):
        for var in ["CLIENT_ID", "CLIENT_SECRET", "REDIRECT_URI"]:
            os.environ.pop(var, None)
        with self.assertRaises(SystemExit) as cm:
            runpy.run_module("ad_radio_playlist", run_name="ad_radio_playlist")
        self.assertIn(
            "Missing environment variables: CLIENT_ID, CLIENT_SECRET, REDIRECT_URI",
            str(cm.exception)
        )

    def test_env_present(self):
        os.environ["CLIENT_ID"] = "id"
        os.environ["CLIENT_SECRET"] = "secret"
        os.environ["REDIRECT_URI"] = "uri"
        ns = runpy.run_module("ad_radio_playlist", run_name="ad_radio_playlist")
        self.assertEqual(ns.get("client_id"), "id")


class TestGetAccessToken(unittest.TestCase):
    def setUp(self):
        os.environ["CLIENT_ID"] = "id"
        os.environ["CLIENT_SECRET"] = "secret"
        os.environ["REDIRECT_URI"] = "uri"
        if "ad_radio_playlist" in globals():
            import importlib, ad_radio_playlist
            importlib.reload(ad_radio_playlist)

    def test_get_access_token_success(self):
        import ad_radio_playlist
        dummy_resp = unittest.mock.Mock()
        dummy_resp.raise_for_status.return_value = None
        dummy_resp.json.return_value = {"access_token": "token123"}
        with patch.object(ad_radio_playlist.requests, "post", return_value=dummy_resp):
            headers = ad_radio_playlist.get_access_token("authcode")
            self.assertEqual(headers, {"Authorization": "Bearer token123"})

    def test_get_access_token_failure(self):
        import ad_radio_playlist
        dummy_resp = unittest.mock.Mock()
        dummy_resp.status_code = 400
        dummy_resp.text = "Bad request"
        dummy_resp.raise_for_status.side_effect = ad_radio_playlist.requests.HTTPError("Bad request")
        with patch.object(ad_radio_playlist.requests, "post", return_value=dummy_resp):
            with self.assertRaises(RuntimeError) as cm:
                ad_radio_playlist.get_access_token("authcode")
            self.assertIn(
                "Failed to get access token (400): Bad request",
                str(cm.exception)
            )


class TestGetPlaylistId(unittest.TestCase):
    def test_get_playlist_id_with_arg(self):
        import ad_radio_playlist
        self.assertEqual(ad_radio_playlist.get_playlist_id("abc"), "abc")

    def test_get_playlist_id_default(self):
        import ad_radio_playlist
        ad_radio_playlist.playlist_id = "xyz"
        self.assertEqual(ad_radio_playlist.get_playlist_id(), "xyz")

class TestGetArtistsSongs(unittest.TestCase):
    def setUp(self):
        self._orig_env = dict(os.environ)
        # ensure module import passes env validation
        os.environ["CLIENT_ID"] = "id"
        os.environ["CLIENT_SECRET"] = "secret"
        os.environ["REDIRECT_URI"] = "uri"
        import importlib, ad_radio_playlist
        importlib.reload(ad_radio_playlist)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_fetch_page_failure(self):
        import ad_radio_playlist
        dummy = unittest.mock.Mock(status_code=500)
        with patch.object(ad_radio_playlist.requests, 'get', return_value=dummy):
            with self.assertRaises(RuntimeError) as cm:
                ad_radio_playlist.get_artists_songs('http://test')
            self.assertIn('Failed to fetch show page (500)', str(cm.exception))

    def test_no_song_list(self):
        import ad_radio_playlist
        dummy = unittest.mock.Mock(status_code=200, content=b'<div class="entry-content">Nothing here</div>')
        with patch.object(ad_radio_playlist.requests, 'get', return_value=dummy):
            with self.assertRaises(RuntimeError) as cm:
                ad_radio_playlist.get_artists_songs('http://test')
            self.assertIn('No song list found on page', str(cm.exception))

    def test_song_list_parse(self):
        import ad_radio_playlist
        html = '<div class="entry-content">SIRIUS ++ Artist A - Song A ++ Artist B - Song B</div>'
        dummy = unittest.mock.Mock(status_code=200, content=html.encode())
        with patch.object(ad_radio_playlist.requests, 'get', return_value=dummy):
            result = ad_radio_playlist.get_artists_songs('http://test')
            self.assertEqual(result, ['Artist A - Song A', 'Artist B - Song B'])
        
class TestCallbackErrorHandling(unittest.TestCase):
    def setUp(self):
        # set required env and reload module
        self._orig_env = dict(os.environ)
        os.environ.update({
            "CLIENT_ID": "id", "CLIENT_SECRET": "secret", "REDIRECT_URI": "uri"
        })
        import importlib, ad_radio_playlist
        importlib.reload(ad_radio_playlist)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_callback_song_list_error(self):
        import ad_radio_playlist
        # stub dependencies
        headers = {"Authorization": "Bearer tok"}
        resp_me = unittest.mock.Mock(status_code=200)
        resp_me.json.return_value = {"id": "user123"}
        with patch.object(ad_radio_playlist, 'get_access_token', return_value=headers), \
             patch.object(ad_radio_playlist, 'get_playlist_id', return_value='pid'), \
             patch.object(ad_radio_playlist.requests, 'get', return_value=resp_me), \
             patch.object(ad_radio_playlist, 'get_latest_episode', return_value='http://test'), \
             patch.object(ad_radio_playlist, 'get_artists_songs', side_effect=RuntimeError('no list')):
            import asyncio
            with self.assertRaises(ad_radio_playlist.HTTPException) as cm:
                asyncio.run(ad_radio_playlist.callback('codeval'))
            exc = cm.exception
            self.assertEqual(exc.status_code, 502)
            self.assertIn('Failed to parse song list', exc.detail)


if __name__ == "__main__":
    unittest.main()