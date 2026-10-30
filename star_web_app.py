#!/usr/bin/env python3
"""
本地网页星图查询工具

运行:
    python star_web_app.py

然后在浏览器访问:
    http://127.0.0.1:8765
"""

from __future__ import annotations

import argparse
import json
import math
import sys

import pandas as pd
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

def _bundle_dir() -> Path:
    """
    随程序打包的资源根目录（HTML 等）:
    - PyInstaller: _MEIPASS
    - 源码: 脚本所在目录
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _app_data_dir() -> Path:
    """
    用户可写数据与星表根目录（不打包）:
    - PyInstaller: 与 exe 同级目录，便于手动放入 local_data/ 等星表目录
    - 源码: 与脚本同级
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


# 默认离线合成演示，不是真实星空；可在页面中选择自己的星表。
DEFAULT_CATALOG = (
    _app_data_dir() / "local_data" / "starcatalogs" / "simplified"
    / "demo" / "res5" / "mag15.0" / "epoch2000.0"
)
HTML_FILE = _bundle_dir() / "star_viewer.html"
PARAMS_FILE = _app_data_dir() / "user_params.json"

_CATALOG_CACHE: dict[str, Any] = {}


def _shortest_delta_ra(ra: float, ra_center: float) -> float:
    """返回相对于中心点的最短 RA 差值，单位度。"""
    return (ra - ra_center + 180.0) % 360.0 - 180.0


def _parse_payload(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"请求体不是合法 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("请求体必须为 JSON 对象")
    return payload


def _atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding=encoding)
    tmp.replace(path)


def _load_saved_params() -> dict[str, Any]:
    try:
        if not PARAMS_FILE.exists():
            return {}
        data = json.loads(PARAMS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _save_params(payload: dict[str, Any]) -> None:
    try:
        # 只保存前端相关的字段，避免把无关内容也写进去
        keys = [
            "catalog_path",
            "h",
            "w",
            "dh_angle",
            "dw_angle",
            "ra",
            "dec",
            "search_radius",
            "mag",
            "max_count",
            "theta",
            "dx",
            "dy",
        ]
        data = {k: payload.get(k) for k in keys if k in payload}
        _atomic_write_text(PARAMS_FILE, json.dumps(data, ensure_ascii=False, indent=2))
    except Exception:  # noqa: BLE001
        # 记录参数失败不应影响主流程
        return


def _required_float(payload: dict[str, Any], key: str) -> float:
    if key not in payload:
        raise ValueError(f"缺少参数: {key}")
    try:
        value = float(payload[key])
        if not math.isfinite(value):
            raise ValueError("必须为有限数值")
        return value
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"参数 {key} 不是数值") from exc


def _required_int(payload: dict[str, Any], key: str) -> int:
    if key not in payload:
        raise ValueError(f"缺少参数: {key}")
    try:
        return int(payload[key])
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"参数 {key} 不是整数") from exc


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    if key not in payload:
        return None
    value = payload[key]
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    try:
        return int(value)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"参数 {key} 不是整数") from exc


def _normalize_catalog_dir(catalog_path: str) -> tuple[str, Path]:
    """
    归一化 catalog 目录路径。
    - 返回可传给 starcatalogquery 的 POSIX 风格目录字符串 (必须以 / 结尾)
    - 同时返回本机绝对路径对象，便于展示给前端
    """
    raw = Path(catalog_path)
    path_obj = raw if raw.is_absolute() else (_app_data_dir() / raw)
    resolved = path_obj.resolve()
    normalized = resolved.as_posix()
    if not normalized.endswith("/"):
        normalized += "/"
    return normalized, resolved


def _load_catalog(catalog_dir_normalized: str):
    try:
        # 延迟导入，避免缺少可选依赖时服务无法启动
        from starlib.starcatalogquery import StarCatalog
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "无法导入 starlib.starcatalogquery（请检查 Python 版本、依赖或缺失的 DLL）。\n"
            f"- 原始异常: {type(exc).__name__}: {exc}\n"
            f"- Python: {sys.version.split()[0]} ({sys.platform})\n"
            "请确认已安装依赖: requirements.txt 中的依赖；healpy 仅用于可选索引功能"
        ) from exc

    if catalog_dir_normalized not in _CATALOG_CACHE:
        _CATALOG_CACHE[catalog_dir_normalized] = StarCatalog.load(catalog_dir_normalized)
    return _CATALOG_CACHE[catalog_dir_normalized]


def _mag_to_color(mag: float, min_mag: float, max_mag: float) -> str:
    """
    星等颜色映射: 亮->红, 中->白, 暗->灰
    """
    if max_mag <= min_mag:
        t = 0.0
    else:
        t = (mag - min_mag) / (max_mag - min_mag)
    t = max(0.0, min(1.0, t))

    red = (255, 64, 64)
    white = (255, 255, 255)
    gray = (128, 128, 128)
    if t <= 0.5:
        k = t / 0.5
        c0, c1 = red, white
    else:
        k = (t - 0.5) / 0.5
        c0, c1 = white, gray
    r = round(c0[0] + (c1[0] - c0[0]) * k)
    g = round(c0[1] + (c1[1] - c0[1]) * k)
    b = round(c0[2] + (c1[2] - c0[2]) * k)
    return f"rgb({r},{g},{b})"


def query_stars(payload: dict[str, Any]) -> dict[str, Any]:
    h = _required_int(payload, "h")
    w = _required_int(payload, "w")
    dh_angle = _required_float(payload, "dh_angle")
    dw_angle = _required_float(payload, "dw_angle")
    ra_center = _required_float(payload, "ra")
    dec_center = _required_float(payload, "dec")
    search_radius = _required_float(payload, "search_radius")
    mag_limit = _required_float(payload, "mag")
    theta = _required_float(payload, "theta")
    dx = _required_float(payload, "dx")
    dy = _required_float(payload, "dy")
    max_count = _optional_int(payload, "max_count")
    catalog_path = str(payload.get("catalog_path", str(DEFAULT_CATALOG)))
    catalog_dir_normalized, catalog_path_resolved = _normalize_catalog_dir(catalog_path)
    if not catalog_path_resolved.is_dir():
        raise ValueError("星表目录不存在；先运行 python -m tools.generate_demo，或选择已有星表目录")

    if h <= 0 or w <= 0:
        raise ValueError("分辨率 h/w 必须 > 0")
    if dh_angle <= 0 or dw_angle <= 0:
        raise ValueError("像素张角 dh_angle/dw_angle 必须 > 0")
    if not (-90.0 <= dec_center <= 90.0):
        raise ValueError("DEC 必须在 [-90, 90] 度")
    if search_radius <= 0:
        raise ValueError("search_radius 必须 > 0")
    if max_count is not None and max_count < 1:
        raise ValueError("max_count 必须 >= 1，留空表示不限制")

    diag_half = 0.5 * math.sqrt((h * dh_angle) ** 2 + (w * dw_angle) ** 2)
    if search_radius <= diag_half:
        raise ValueError(
            f"搜索半径 {search_radius:.4f} 度过小，应大于相机对角线半径 {diag_half:.4f} 度"
        )

    starcat = _load_catalog(catalog_dir_normalized)
    stars = starcat.search_cone([ra_center, dec_center], search_radius, max_num=None)
    df = stars.df.copy()

    if df.empty:
        return {
            "stars": [],
            "count": 0,
            "diag_half_radius": diag_half,
            "catalog_path": str(catalog_path_resolved),
        }

    # 可见星等上限：只保留 mag <= mag_limit（数值越小越亮；不设则无法在锥搜后裁剪暗星）
    df["mag"] = pd.to_numeric(df["mag"], errors="coerce")
    df = df.dropna(subset=["mag"])
    df = df[df["mag"] <= mag_limit]
    df = df.reset_index(drop=True)

    if df.empty:
        return {
            "stars": [],
            "count": 0,
            "diag_half_radius": diag_half,
            "catalog_path": str(catalog_path_resolved),
        }

    delta_ra = [_shortest_delta_ra(float(v), ra_center) for v in df["ra"].values]
    cos_dec = math.cos(math.radians(dec_center))

    projected_x = []
    projected_y = []
    projected_dist = []
    for dra, dec_v in zip(delta_ra, df["dec"].values):
        x_deg = float(dra) * cos_dec
        y_deg = float(dec_v - dec_center)
        projected_x.append(x_deg)
        projected_y.append(y_deg)
        projected_dist.append(math.hypot(x_deg, y_deg))

    df["proj_x_deg"] = projected_x
    df["proj_y_deg"] = projected_y
    df["distance_to_center"] = projected_dist
    df = df.sort_values("distance_to_center")
    if max_count is not None:
        df = df.head(max_count)
    df = df.reset_index(drop=True)

    cx = w / 2.0
    cy = h / 2.0
    rad = math.radians(theta)
    cos_t = math.cos(rad)
    sin_t = math.sin(rad)

    x_pixels = cx + df["proj_x_deg"].values / dw_angle
    y_pixels = cy - df["proj_y_deg"].values / dh_angle
    x0 = x_pixels - cx
    y0 = y_pixels - cy
    x_rot = cx + cos_t * x0 - sin_t * y0 + dx
    y_rot = cy + sin_t * x0 + cos_t * y0 + dy

    min_mag = float(df["mag"].min())
    max_mag = float(df["mag"].max())

    star_list = []
    for idx, row in df.iterrows():
        star_list.append(
            {
                "id": int(idx),
                "ra": float(row["ra"]),
                "dec": float(row["dec"]),
                "mag": float(row["mag"]),
                "distance_to_center": float(row["distance_to_center"]),
                "x": float(x_rot[idx]),
                "y": float(y_rot[idx]),
                "visible_in_frame": bool(0 <= x_rot[idx] <= w and 0 <= y_rot[idx] <= h),
                "color": _mag_to_color(float(row["mag"]), min_mag, max_mag),
            }
        )

    return {
        "stars": star_list,
        "count": len(star_list),
        "diag_half_radius": diag_half,
        "catalog_path": str(catalog_path_resolved),
    }


class StarWebHandler(BaseHTTPRequestHandler):
    def _json(self, payload: dict[str, Any], status: int = HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            if not HTML_FILE.exists():
                self._json({"ok": False, "error": f"找不到页面文件: {HTML_FILE}"}, HTTPStatus.NOT_FOUND)
                return
            content = HTML_FILE.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if parsed.path == "/healthz":
            self._json({"ok": True})
            return
        if parsed.path == "/api/params":
            self._json({"ok": True, "params": _load_saved_params()})
            return
        self._json({"ok": False, "error": "Not Found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path not in ("/api/query", "/api/params"):
            self._json({"ok": False, "error": "Not Found"}, HTTPStatus.NOT_FOUND)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            payload = _parse_payload(raw_body)
            if parsed.path == "/api/params":
                _save_params(payload)
                self._json({"ok": True})
                return

            _save_params(payload)
            result = query_stars(payload)
            self._json({"ok": True, "result": result})
        except ValueError as exc:
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            self._json({"ok": False, "error": f"服务内部错误: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> int:
    parser = argparse.ArgumentParser(description="本地网页星图查询服务")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=8765, help="监听端口")
    args = parser.parse_args()

    if not HTML_FILE.exists():
        print(f"[ERROR] 页面文件不存在: {HTML_FILE}", file=sys.stderr)
        return 1

    server = ThreadingHTTPServer((args.host, args.port), StarWebHandler)
    print(f"Star web app running at http://{args.host}:{args.port}")
    print(f"Default catalog: {DEFAULT_CATALOG}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
