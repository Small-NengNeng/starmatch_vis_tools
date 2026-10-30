"""Offline integration checks using synthetic inputs only."""
from __future__ import annotations

import contextlib
import io
import json
import math
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import star_web_app as app
from starlib.starcatalogquery import StarCatalog
from tools.generate_demo import generate_demo, synthetic_stars

ROOT = Path(__file__).resolve().parents[1]


class PublicReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="starmatch-tests-")
        cls.folder = Path(cls.temp.name)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            cls.catalog = generate_demo(cls.folder / "local_data")
        cls.defaults = json.loads((ROOT / "user_params.example.json").read_text(encoding="utf-8"))
        cls.defaults["catalog_path"] = str(cls.catalog)
        cls.param_patch = patch.object(app, "PARAMS_FILE", cls.folder / "user_params.json")
        cls.param_patch.start()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.StarWebHandler)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join(timeout=5)
        cls.param_patch.stop()
        app._CATALOG_CACHE.clear()
        cls.temp.cleanup()

    def payload(self, **overrides):
        return self.defaults | overrides

    def request(self, path, payload=None):
        req = Request(self.base + path, data=None if payload is None else json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=15) as res:
                return res.status, res.read()
        except HTTPError as exc:
            return exc.code, exc.read()

    def test_synthetic_catalog_and_sorted_query(self):
        self.assertEqual(len(list(self.catalog.glob("*.csv"))), 2592)
        result = app.query_stars(self.payload())
        self.assertEqual(result["count"], 169)
        self.assertEqual(result["count"], len(synthetic_stars()))
        distances = [s["distance_to_center"] for s in result["stars"]]
        self.assertEqual(distances, sorted(distances))
        catalog = StarCatalog.load(self.catalog.as_posix() + "/")
        self.assertTrue(catalog.validity)
        self.assertIn("Synthetic", catalog.description)

    def test_magnitude_and_count(self):
        result = app.query_stars(self.payload(mag=6))
        self.assertEqual(result["count"], sum(s["mag"] <= 6 for s in synthetic_stars()))
        self.assertTrue(all(s["mag"] <= 6 for s in result["stars"]))
        limited = app.query_stars(self.payload(mag=6, max_count=7))
        self.assertEqual(limited["count"], 7)
        positions = lambda stars: [(s["ra"], s["dec"], s["mag"]) for s in stars]
        self.assertEqual(positions(limited["stars"]), positions(result["stars"][:7]))

    def test_rotation_and_translation(self):
        original = app.query_stars(self.payload())["stars"]
        moved = app.query_stars(self.payload(theta=90, dx=12, dy=-8))["stars"]
        for before, after in zip(original, moved):
            self.assertAlmostEqual(after["x"], 512 - (before["y"] - 512) + 12)
            self.assertAlmostEqual(after["y"], 512 + (before["x"] - 512) - 8)

    def test_empty_sky_and_filter(self):
        self.assertEqual(app.query_stars(self.payload(ra=180))["count"], 0)
        self.assertEqual(app.query_stars(self.payload(mag=-10))["count"], 0)

    def test_invalid_inputs_and_missing_catalog(self):
        for invalid in ({"h": 0}, {"dec": 91}, {"search_radius": 1}, {"max_count": 0},
                        {"ra": "nan"}, {"theta": "inf"}, {"mag": "not-a-number"},
                        {"catalog_path": str(self.folder / "missing")}):
            with self.subTest(invalid=invalid):
                code, body = self.request("/api/query", self.payload(**invalid))
                self.assertEqual(code, 400, body)
                self.assertFalse(json.loads(body)["ok"])

    def test_http_page_health_query_and_params(self):
        status, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("非真实星空", body.decode())
        self.assertEqual(json.loads(self.request("/healthz")[1]), {"ok": True})
        status, body = self.request("/api/query", self.payload(max_count=3))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["result"]["count"], 3)
        self.assertEqual(self.request("/api/params", self.payload(dx=42))[0], 200)
        saved = json.loads(self.request("/api/params")[1])["params"]
        self.assertEqual(saved["dx"], 42)
        self.assertEqual(self.request("/not-found")[0], 404)
        self.assertEqual(self.request("/api/query", [1, 2])[0], 400)

    def test_short_tile_and_2mass_prefix_compatibility(self):
        path = self.folder / "legacy" / "starcatalogs/simplified/2mass_hmag/res5/magfull.0/epoch2000.0"
        path.mkdir(parents=True, exist_ok=True)
        (path / "2mass-1314.csv").write_text("90,0,5\n", encoding="utf-8")
        result = app.query_stars(self.payload(catalog_path=str(path)))
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["stars"][0]["mag"], 5)

    def test_build_cli(self):
        source = self.folder / "input.json"
        source.write_text(json.dumps(synthetic_stars()), encoding="utf-8")
        result = subprocess.run([sys.executable, "-m", "tools.build_starcat", "--input", str(source),
                                 "--name", "demo", "--output-dir", str(self.folder / "cli")],
                                cwd=ROOT, capture_output=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        source.write_text("{}", encoding="utf-8")
        failed = subprocess.run([sys.executable, "-m", "tools.build_starcat", "--input", str(source)],
                                cwd=ROOT, capture_output=True, timeout=30)
        self.assertNotEqual(failed.returncode, 0)

    def test_download_adapter_without_network(self):
        # The core test suite also runs without the optional download dependency.
        try:
            from tools.get8star_json import get_magnitude_stars, save_to_json
        except ModuleNotFoundError as exc:
            if exc.name and exc.name.startswith("astroquery"):
                self.skipTest("optional astroquery is not installed")
            raise
        from astropy.table import Table
        table = Table({"RAICRS": [90.0, 91.0], "DEICRS": [0.0, 1.0], "Vmag": [5.0, float("nan")]})
        with patch("tools.get8star_json.Vizier.query_constraints", return_value=[table]) as query:
            stars = get_magnitude_stars(6, "I/239/hip_main", "Vmag")
        query.assert_called_once_with(catalog="I/239/hip_main", Vmag="<=6")
        self.assertEqual(stars, [{"ra": 90.0, "dec": 0.0, "mag": 5.0}])
        output = self.folder / "download.json"
        save_to_json(stars, output)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), stars)

    def test_default_paths_match(self):
        defaults = json.loads((ROOT / "user_params.example.json").read_text(encoding="utf-8"))
        self.assertEqual(app.DEFAULT_CATALOG, ROOT / defaults["catalog_path"])
        html = (ROOT / "star_viewer.html").read_text(encoding="utf-8")
        self.assertIn(defaults["catalog_path"], html)

    def test_tool_entrypoints(self):
        for module in ("tools.generate_demo", "tools.build_starcat", "tools.catalog_stats"):
            with self.subTest(module=module):
                result = subprocess.run([sys.executable, "-m", module, "--help"], cwd=ROOT,
                                        capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, "-m", "tools.catalog_stats", "--dir", str(self.catalog), "--summary"],
                                cwd=ROOT, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
