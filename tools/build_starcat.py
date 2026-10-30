#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将JSON格式的星表数据转换为starcatalogquery所需的瓦片CSV格式

格式说明见 docs/data.md：
- CSV文件无表头，三列：ra, dec, mag
- ra和dec保留6位小数，mag保留1位小数
- 文件命名：{sc_name}-{seq_index}.csv
- tile_size=5时，总瓦片数 = 2592
"""

import argparse
import json
import pandas as pd
import numpy as np
import os
from pathlib import Path
from tqdm import tqdm

ROOT_DIR = Path(__file__).resolve().parents[1]


def build_tiles_from_json(
    json_path,
    sc_name='hip',
    tile_size=5,
    mag_threshold=15.0,
    epoch=2000.0,
    output_base_dir=str(ROOT_DIR / 'local_data')
):
    """
    从JSON文件构建瓦片结构

    参数:
        json_path: JSON文件路径
        sc_name: 星表名称（用于文件命名）
        tile_size: 瓦片大小（度）
        mag_threshold: 星等阈值
        epoch: 历元
        output_base_dir: 输出基础目录
    """
    if tile_size not in (1, 2, 3, 5, 6, 9, 10):
        raise ValueError("tile_size 必须为 1/2/3/5/6/9/10")
    if not sc_name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in sc_name):
        raise ValueError("星表名只允许英文字母、数字、下划线和连字符")
    if mag_threshold is None or not np.isfinite(mag_threshold) or not np.isfinite(epoch):
        raise ValueError("mag_threshold 和 epoch 必须为有限数值")
    print(f"读取JSON文件: {json_path}")

    # 读取JSON数据
    with open(json_path, 'r', encoding='utf-8') as f:
        stars_data = json.load(f)

    print(f"共读取 {len(stars_data)} 颗恒星")

    # 转换为DataFrame
    if not isinstance(stars_data, list):
        raise ValueError("输入 JSON 必须是包含 ra/dec/mag 的对象数组")
    df = pd.DataFrame(stars_data) if stars_data else pd.DataFrame(columns=['ra', 'dec', 'mag'])

    # 检查必需的列
    required_cols = ['ra', 'dec', 'mag']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"JSON文件缺少必需的列: {missing_cols}")

    # 数据预处理
    print("数据预处理...")

    df[required_cols] = df[required_cols].apply(pd.to_numeric, errors='coerce')
    df[required_cols] = df[required_cols].replace([np.inf, -np.inf], np.nan)
    # 过滤掉包含 NaN 或无效值的数据
    initial_count = len(df)
    df = df.dropna(subset=['ra', 'dec', 'mag']).copy()
    if len(df) < initial_count:
        print(f"过滤掉 {initial_count - len(df)} 颗包含无效值的恒星")

    # 确保ra在0-360范围内
    df['ra'] = df['ra'] % 360

    # 确保dec在-90到90范围内
    df['dec'] = df['dec'].clip(-90, 90)

    # 过滤星等
    if mag_threshold is not None:
        df = df[df['mag'] < mag_threshold].copy()
        print(f"过滤后剩余 {len(df)} 颗恒星（mag < {mag_threshold}）")

    # 按星等排序（从亮到暗）
    df = df.sort_values(by='mag').reset_index(drop=True)

    # 精度处理
    df['ra'] = df['ra'].round(6)
    df['dec'] = df['dec'].round(6)
    df['mag'] = df['mag'].round(1)

    # 计算每个恒星所属的瓦片索引
    print("计算瓦片索引...")
    count_lon = 360 // tile_size
    codec = 90 - df['dec'].values
    # 使用 np.nan_to_num 处理可能的 NaN，并确保索引在有效范围内
    ra_seq = np.clip((df['ra'].values // tile_size).astype(int), 0, count_lon - 1)
    codec_seq = np.clip((codec // tile_size).astype(int), 0, (180 // tile_size) - 1)
    df['seq_index'] = codec_seq * count_lon + ra_seq

    # 确保索引在有效范围内
    max_seq = (180 // tile_size) * (360 // tile_size) - 1
    df['seq_index'] = df['seq_index'].clip(0, max_seq)

    # 创建输出目录
    output_dir = os.path.join(
        output_base_dir,
        'starcatalogs',
        'simplified',
        sc_name,
        f'res{tile_size}',
        f'mag{mag_threshold:.1f}',
        f'epoch{epoch:.1f}'
    )
    os.makedirs(output_dir, exist_ok=True)
    print(f"输出目录: {output_dir}")

    # 计算总瓦片数
    total_tiles = (180 // tile_size) * (360 // tile_size)
    print(f"总瓦片数: {total_tiles}")

    # 按瓦片分组
    print("按瓦片分组并保存...")
    grouped = df.groupby('seq_index')

    # 统计每个瓦片的恒星数量
    tile_counts = grouped.size()

    # 保存所有瓦片文件
    saved_count = 0
    empty_count = 0

    for seq_index in tqdm(range(total_tiles), desc="生成瓦片文件"):
        filename = os.path.join(output_dir, f'{sc_name}-{seq_index}.csv')

        if seq_index in tile_counts.index:
            # 有数据的瓦片
            tile_data = grouped.get_group(seq_index)
            tile_data = tile_data[['ra', 'dec', 'mag']]
            tile_data.to_csv(filename, index=False, header=False)
            saved_count += 1
        else:
            # 空瓦片（创建空文件）
            with open(filename, 'w') as f:
                f.write('')  # 空文件
            empty_count += 1

    print(f"\n构建完成！")
    print(f"  - 有数据的瓦片: {saved_count}")
    print(f"  - 空瓦片: {empty_count}")
    print(f"  - 总瓦片数: {total_tiles}")
    print(f"  - 输出目录: {output_dir}")

    return output_dir


def verify_tiles(output_dir, tile_size, sc_name='hip'):
    """
    验证生成的瓦片文件
    """
    print("\n验证瓦片文件...")

    from glob import glob
    import os

    # 手动验证文件数量
    pattern = os.path.join(output_dir, f'{sc_name}-*.csv')
    files = glob(pattern)
    file_num = len(files)

    expected = (180 // tile_size) * (360 // tile_size)

    print(f"文件数量: {file_num}")
    print(f"期望文件数: {expected}")

    if file_num == expected:
        # 计算目录大小
        dir_size = sum([os.path.getsize(f)/1024 for f in files])
        if dir_size < 1024:
            dir_size_str = '{:.1f} KB'.format(dir_size)
        elif dir_size < 1024**2:
            dir_size_str = '{:.1f} MB'.format(dir_size/1024)
        else:
            dir_size_str = '{:.1f} GB'.format(dir_size/1024**2)
        print(f"目录大小: {dir_size_str}")
        print("✓ 瓦片文件验证通过！")
        return True
    else:
        print(f"✗ 瓦片文件验证失败！")
        print(f"  期望文件数: {expected}, 实际文件数: {file_num}")

        # 检查缺失的文件
        existing_indices = set()
        for f in files:
            basename = os.path.basename(f)
            idx = int(basename.replace(f'{sc_name}-', '').replace('.csv', ''))
            existing_indices.add(idx)

        missing = set(range(expected)) - existing_indices
        if len(missing) <= 10:
            print(f"  缺失的文件索引: {sorted(missing)}")
        else:
            print(f"  缺失的文件索引: {len(missing)} 个（前10个: {sorted(list(missing))[:10]}）")

        return False


def verify_with_starquery(output_dir, sc_name, tile_size, mag_threshold, epoch):
    """
    使用 StarCatalogSimplified.load() 进行二次验证
    """
    print("\n" + "="*60)
    print("使用 StarCatalogSimplified 进行二次验证...")
    print("="*60)

    try:
        from starlib.starcatalogquery.classes import StarCatalogSimplified

        print(f"尝试加载星表...")
        print(f"  路径: {output_dir}")
        print(f"  星表名: {sc_name}")
        print(f"  瓦片大小: {tile_size}")
        print(f"  星等阈值: {mag_threshold}")
        print(f"  历元: {epoch}")

        sc_simplified = StarCatalogSimplified.load(
            sc_name,
            tile_size,
            mag_threshold,
            epoch,
            Path(output_dir).resolve().as_posix().rstrip("/") + "/"
        )

        print("\n✓ 星表加载成功！")
        print(f"\n星表信息:")
        print(f"  - 星表对象: {sc_simplified}")
        print(f"  - 瓦片目录: {sc_simplified.tiles_dir}")
        print(f"  - 瓦片数量: {sc_simplified.tiles_num}")
        print(f"  - 瓦片大小: {sc_simplified.tile_size}")
        print(f"  - 目录大小: {sc_simplified.sc_size}")
        print(f"  - 有效性: {sc_simplified.validity}")

        # 测试查询功能
        print(f"\n测试查询功能...")
        try:
            # 测试 cone search
            test_center = [120.0, 30.0]  # 测试坐标
            test_radius = 5.0  # 5度半径
            stars = sc_simplified.search_cone(test_center, test_radius, max_num=10)
            print(f"  ✓ Cone search 测试成功")
            print(f"    查询中心: {test_center}, 半径: {test_radius}度")
            print(f"    找到恒星数: {stars.num_stars}")

            # 测试 box search
            test_box = [115.0, 25.0, 125.0, 35.0]  # [ra_min, dec_min, ra_max, dec_max]
            stars_box = sc_simplified.search_box(test_box, max_num=10)
            print(f"  ✓ Box search 测试成功")
            print(f"    查询区域: {test_box}")
            print(f"    找到恒星数: {stars_box.num_stars}")

            print(f"\n✓ 所有验证测试通过！星表可以正常使用。")
            return True

        except Exception as e:
            print(f"  ✗ 查询测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    except ImportError as e:
        print(f"✗ 无法导入 starlib.starcatalogquery: {e}")
        print("  请确保在项目根目录运行脚本，且 starlib 目录可被 Python 导入")
        return False
    except Exception as e:
        print(f"✗ 星表加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="将 ra/dec/mag JSON 转成矩形 CSV 星表瓦片")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--name", default="hip", choices=["hip", "demo", "2mass", "2mass_hmag", "hygv35", "gaiadr3", "ucac5", "usnob", "gsc12", "gsc242"])
    parser.add_argument("--tile-size", type=int, default=5, choices=[1, 2, 3, 5, 6, 9, 10])
    parser.add_argument("--max-magnitude", type=float, default=15.0)
    parser.add_argument("--epoch", type=float, default=2000.0)
    parser.add_argument("--output-dir", type=Path, default=ROOT_DIR / "local_data")
    args = parser.parse_args()
    try:
        output = build_tiles_from_json(args.input, args.name, args.tile_size, args.max_magnitude, args.epoch, args.output_dir)
        valid = verify_tiles(output, args.tile_size, args.name)
        if valid:
            valid = verify_with_starquery(output, args.name, args.tile_size, args.max_magnitude, args.epoch)
        if valid:
            print("网页 catalog_path: " + str(Path(output).resolve()))
        return 0 if valid else 1
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(1, f"构建失败: {exc}\n")


if __name__ == '__main__':
    raise SystemExit(main())
