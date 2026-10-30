"""Generate deterministic synthetic stars, NOT real sky observations."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from tools.build_starcat import build_tiles_from_json, verify_tiles

ROOT = Path(__file__).resolve().parents[1]


def synthetic_stars() -> list[dict[str, float]]:
    # An artificial grid around RA=90, DEC=0; no real catalog is consulted.
    return [
        {"ra": round(90 + col * 0.65 + row * 0.013, 6),
         "dec": round(row * 0.63 + col * 0.017, 6),
         "mag": round(2.0 + ((row + 6) * 13 + col + 6) % 120 / 10, 1)}
        for row in range(-6, 7) for col in range(-6, 7)
    ]


def generate_demo(output_dir: Path = ROOT / "local_data") -> Path:
    with tempfile.TemporaryDirectory(prefix="starmatch-demo-") as folder:
        data_file = Path(folder) / "synthetic.json"
        data_file.write_text(json.dumps(synthetic_stars()), encoding="utf-8")
        result = build_tiles_from_json(data_file, sc_name="demo", output_base_dir=output_dir)
    if not verify_tiles(result, 5, "demo"):
        raise RuntimeError("演示瓦片验证失败")
    return Path(result)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成人工合成演示：非真实星空，不需要联网")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "local_data")
    args = parser.parse_args()
    result = generate_demo(args.output_dir)
    print(f"非真实星空演示已生成：{result}")
    print("网页默认参数：RA=90、DEC=0、搜索半径=10 度；python star_web_app.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
