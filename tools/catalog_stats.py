#!/usr/bin/env python3
# 批量统计 simplified 星表 CSV（无表头: ra,dec,mag）中每文件的 RA/DEC 范围与跨度。
# 示例单文件:
#   .../epoch2000.0/2mass-12274.csv

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def default_catalog_dir() -> Path:
    return (
        Path(__file__).resolve().parents[1] / "local_data" / "starcatalogs"
        / "simplified" / "demo" / "res5" / "mag15.0" / "epoch2000.0"
    )


TILE_CSV = re.compile(r"^.+-\d+\.csv$", re.IGNORECASE)


def file_radec_stats(path: Path) -> dict:
    """返回单文件 ra/dec 最小最大值与跨度（度）。"""
    df = pd.read_csv(
        path,
        header=None,
        usecols=[0, 1],
        dtype=np.float64,
        names=["ra", "dec"],
        comment="#",
    )
    ra, dec = df["ra"].to_numpy(), df["dec"].to_numpy()
    ra_min, ra_max = float(np.nanmin(ra)), float(np.nanmax(ra))
    dec_min, dec_max = float(np.nanmin(dec)), float(np.nanmax(dec))
    return {
        "path": path,
        "n": int(len(df)),
        "ra_min": ra_min,
        "ra_max": ra_max,
        "dec_min": dec_min,
        "dec_max": dec_max,
        "d_ra": ra_max - ra_min,
        "d_dec": dec_max - dec_min,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="批量统计星表 CSV 的 RA/DEC 范围与宽度")
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="星表目录（默认: local_data/.../demo/.../epoch2000.0）",
    )
    parser.add_argument(
        "--glob",
        default="*.csv",
        help="匹配文件名模式，默认 *.csv",
    )
    parser.add_argument(
        "--first",
        type=int,
        default=0,
        metavar="N",
        help="只处理按文件名排序后的前 N 个 CSV（0 表示全部）",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="处理完后额外打印全局汇总",
    )
    args = parser.parse_args()

    root = args.dir if args.dir is not None else default_catalog_dir()
    if not root.is_dir():
        print(f"[ERROR] 目录不存在: {root}", file=sys.stderr)
        return 1

    files = sorted(root.glob(args.glob))
    files = [p for p in files if p.is_file() and TILE_CSV.match(p.name)]
    if args.first > 0:
        files = files[: args.first]

    if not files:
        print(f"[ERROR] 未找到匹配文件: {root} / {args.glob}", file=sys.stderr)
        return 1

    rows = []
    for p in files:
        try:
            st = file_radec_stats(p)
            rows.append(st)
            # 每处理完一个 CSV 立即输出一行
            print(
                f"{st['path'].name}\t"
                f"n={st['n']}\t"
                f"ra=[{st['ra_min']:.6f},{st['ra_max']:.6f}]\t"
                f"dec=[{st['dec_min']:.6f},{st['dec_max']:.6f}]\t"
                f"d_ra={st['d_ra']:.6f}\t"
                f"d_dec={st['d_dec']:.6f}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] 跳过 {p.name}: {exc}", file=sys.stderr)

    if not rows:
        return 1

    if not args.summary:
        return 0

    all_ra_min = min(r["ra_min"] for r in rows)
    all_ra_max = max(r["ra_max"] for r in rows)
    all_dec_min = min(r["dec_min"] for r in rows)
    all_dec_max = max(r["dec_max"] for r in rows)
    med_d_ra = float(np.median([r["d_ra"] for r in rows]))
    med_d_dec = float(np.median([r["d_dec"] for r in rows]))

    print()
    print("=== 汇总（当前批次） ===")
    print(f"文件数: {len(rows)}")
    print(
        f"全局 RA  : [{all_ra_min:.6f}, {all_ra_max:.6f}]  跨度 {all_ra_max - all_ra_min:.6f} deg"
    )
    print(
        f"全局 DEC: [{all_dec_min:.6f}, {all_dec_max:.6f}]  跨度 {all_dec_max - all_dec_min:.6f} deg"
    )
    print(f"单文件 d_RA  中位数: {med_d_ra:.6f} deg")
    print(f"单文件 d_DEC 中位数: {med_d_dec:.6f} deg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
