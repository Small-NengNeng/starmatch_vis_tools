"""从 VizieR 下载指定星表的 ra/dec/mag，原始数据不随仓库分发。"""
# 关于星表编号说明：
# I/239/hip_main 中的含义：
#   - I/239: Vizier目录编号，I表示"Identification and Position Data"类别
#   - hip_main: Hipparcos星表的主表
#   - 依巴谷星表是欧洲空间局的高精度天体测量任务，提供了高精度的恒星位置和亮度数据
#
# 其他常用星表：
#   - V/50/catalog: Yale Bright Star Catalog（耶鲁亮星表）
#   - I/355/gaiadr3: GAIA DR3（欧洲空间局的现代高精度星表）
#   - I/259/tyc2: Tycho-2星表（依巴谷任务的副产品，包含更多恒星）

import argparse
from pathlib import Path

import numpy as np
import json
import os
from astroquery.vizier import Vizier

def get_magnitude_stars(max_magnitude=15, catalog_name="I/239/hip_main", mag_column="Vmag"):
    """
    从Vizier数据库查询指定星等及更亮的恒星数据
    返回包含赤经、赤纬、星等的列表

    参数:
        catalog_name: 星表名称，默认使用依巴谷星表
        常用星表:
        - "I/239/hip_main": 依巴谷星表（Hipparcos Catalog）- 推荐

    """
    print(f"正在查询{max_magnitude}等及更亮的恒星数据...")
    print(f"使用星表: {catalog_name}")

    # 设置不限制返回行数
    Vizier.ROW_LIMIT = -1

    # 查询星表
    try:
        # 大部分常见亮星表支持 Vmag 过滤
        res = Vizier.query_constraints(catalog=catalog_name, **{mag_column: f"<={max_magnitude}"})
        if res is None or len(res) == 0:
            print("查询失败: 没有返回数据")
            return None
        STAR = res[0]
        print(f"查询成功！找到 {len(STAR)} 颗恒星")
    except Exception as e:
        print(f"查询失败: {e}")
        return None

    # 打印可用的列名（用于调试）
    print(f"可用列名: {list(STAR.columns.keys())}")

    # 尝试不同的列名组合（不同星表可能使用不同的列名）
    ra = None
    dec = None
    mag = None

    # 尝试常见的赤经列名
    for ra_col in ['RAICRS', 'RAJ2000', 'RA', 'RAdeg', 'RA_ICRS','RA_ICRS']:
        if ra_col in STAR.columns:
            ra = np.ma.filled(np.ma.asarray(STAR[ra_col], dtype=float), np.nan)
            print(f"使用赤经列: {ra_col}")
            break

    # 尝试常见的赤纬列名
    for dec_col in ['DEICRS', 'DEJ2000', 'DE', 'Dec', 'DEdeg','DE_ICRS' ,'DE_ICRS']:
        if dec_col in STAR.columns:
            dec = np.ma.filled(np.ma.asarray(STAR[dec_col], dtype=float), np.nan)
            print(f"使用赤纬列: {dec_col}")
            break

    # 尝试常见的星等列名
    for mag_col in [mag_column]:
        if mag_col in STAR.columns:
            mag = np.ma.filled(np.ma.asarray(STAR[mag_col], dtype=float), np.nan)
            print(f"使用星等列: {mag_col}")
            break

    # 检查是否成功获取所有必需的数据
    if ra is None or dec is None or mag is None:
        print("错误: 无法找到必需的列（赤经、赤纬、星等）")
        print(f"请检查星表 {catalog_name} 的列名")
        return None

    valid = np.isfinite(ra) & np.isfinite(dec) & np.isfinite(mag)
    ra, dec, mag = ra[valid], dec[valid], mag[valid]
    if len(ra) == 0:
        print("没有有效恒星数据")
        return None

    # 转换为列表格式，便于JSON序列化
    stars_data = []
    for i in range(len(ra)):
        stars_data.append({
            'ra': float(ra[i]),        # 赤经（度）
            'dec': float(dec[i]),      # 赤纬（度）
            'mag': float(mag[i])       # 视星等
        })

    print(f"星等范围: {mag.min():.2f} 到 {mag.max():.2f}")

    return stars_data

# 查询从-1到指定阈值各等级下星的数目（可后续扩展）

def save_to_json(stars_data, output_path):
    """
    将恒星数据保存到JSON文件

    参数:
        stars_data: 恒星数据列表
        output_path: 输出文件路径
    """
    # 确保输出目录存在
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # 保存为JSON格式
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(stars_data, f, indent=2, ensure_ascii=False)

    print(f"数据已保存到: {output_path}")
    print(f"共保存 {len(stars_data)} 颗恒星的数据")

def list_available_catalogs():
    """
    列出可用的星表
    """
    print("\n=== 常用星表列表 ===")
    catalogs_info = {
        "I/239/hip_main": {
            "name": "依巴谷星表 (Hipparcos Catalog)",
            "description": "高精度星表，包含约11.8万颗恒星，星等范围约-1到12等",
            "columns": "RAICRS, DEICRS, Vmag"
        },
        "V/50/catalog": {
            "name": "Yale Bright Star Catalog",
            "description": "亮星表，包含约9000颗亮于6.5等的恒星",
            "columns": "RAJ2000, DEJ2000, Vmag"
        },
        "I/355/gaiadr3": {
            "name": "GAIA DR3 星表",
            "description": "现代高精度星表，包含超过18亿颗恒星，使用Gmag而不是Vmag",
            "columns": "RA_ICRS, DE_ICRS, Gmag"
        }
    }

    for cat_id, info in catalogs_info.items():
        print(f"\n星表ID: {cat_id}")
        print(f"  名称: {info['name']}")
        print(f"  说明: {info['description']}")
        print(f"  主要列: {info['columns']}")

def main() -> int:
    parser = argparse.ArgumentParser(description="从 VizieR 下载星表（需要联网）")
    parser.add_argument("--catalog", default="I/239/hip_main", help="VizieR 星表编号")
    parser.add_argument("--max-magnitude", type=float, default=15.0)
    parser.add_argument("--mag-column", default="Vmag", help="过滤并导出的星等列，如 Vmag 或 Gmag")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "stardb_download" / "stars_15mag.json")
    args = parser.parse_args()
    if not np.isfinite(args.max_magnitude):
        parser.error("max-magnitude 必须为有限数值")
    stars = get_magnitude_stars(args.max_magnitude, args.catalog, args.mag_column)
    if stars is None:
        return 1
    save_to_json(stars, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
