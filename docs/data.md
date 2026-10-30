# 数据准备

## 离线合成演示

在仓库根目录运行 `python -m tools.generate_demo`。生成器创建 RA=90°、DEC=0° 附近的 169 个确定性人工点，以及完整的 2592 个矩形瓦片文件（大多数为空）。这些点不对应真实恒星。

输出默认位于 `local_data/`；使用 `--output-dir` 可改变数据根目录。目录应可写。生成后的 CSV 不纳入 Git，仓库仅保存生成程序。

## 自行下载真实星表

先安装 `requirements-download.txt`，再运行：

```powershell
python -m tools.get8star_json --catalog I/239/hip_main --max-magnitude 15 --mag-column Vmag --output stardb_download/hip.json
python -m tools.build_starcat --input stardb_download/hip.json --name hip --tile-size 5 --max-magnitude 15 --epoch 2000 --output-dir local_data
```

下载器通过 VizieR 请求数据，需要联网。`--catalog` 是 VizieR 编号，`--mag-column` 必须是该表存在的星等列；RA/DEC 必须是能识别的十进制度坐标列。默认示例使用 Hipparcos 的 Vmag，不保证任意星表都兼容；超大星表应先在外部按需处理。不要把 V/G/H 波段直接视为相同星等。

下载器采用 `mag <= 阈值`，现有瓦片构建器采用 `mag < 阈值`；页面再按 `mag <= 显示上限` 筛选。构建阈值越低，会永久排除更多输入记录。设置高阈值不改变源星表本身的观测深度。

## 输入与输出格式

构建输入为 JSON 对象数组，最少包含以下字段（示例数字为人工值）：

```json
[{"ra": 90.123456, "dec": 0.234567, "mag": 6.5}]
```

构建器舍弃缺失和非有限数值，RA 归一化至 [0,360)，DEC 沿用原工具裁剪至 [-90,90] 的行为。`--epoch` 是目录标签，不会执行自行或历元转换；输入坐标应已处于需要的参考系和历元。

```text
local_data/starcatalogs/simplified/hip/res5/mag15.0/epoch2000.0/
  hip-0.csv
  hip-1.csv
  ...
  hip-2591.csv
```

CSV 无表头，三列依次为 `ra,dec,mag`。文件名为 `{星表名}-{序号}.csv`。瓦片大小为度，允许 1、2、3、5、6、9、10；总数为 `(180 / tile_size) × (360 / tile_size)`。重复构建会覆盖同名输出瓦片。

保留本地查询库对 `2mass_hmag`、`magfull.0` 以及 CSV 前缀与目录名不同的兼容处理。已有 2MASS 数据可直接在页面指定目录；本仓库未提供真实 2MASS 数据或专用全量下载流程。

## 格式限制

该版本使用旧式经纬网矩形瓦片，**不是 HEALPix**，不能混用相同 `res5` 名称下的不同分块规则。当前上游 STARQUERY 的数据结构与此版本不同，使用本仓库内置的 `starlib`。

统计命令：`python -m tools.catalog_stats --dir <星表目录> --summary`。空瓦片自动跳过，所有瓦片均为空时返回非零退出码。

选择不存在的数据目录时页面会提示准备数据；合法星表中的空天区返回零颗恒星。运行中替换数据后需要重启服务以刷新缓存。
