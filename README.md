# StarMatch Vis Tools

本地运行的星图查询与可视化工具：按赤经、赤纬和半径查询离线星表，将恒星投影到像素平面，支持星等筛选、旋转平移、点选、框选和 CSV 导出。

**默认演示完全由程序人工生成，非真实星空，不可用于天文测量。** 仓库不包含真实星表、实验图像、历史结果或可执行文件。

## Windows 快速开始

使用 Python 3.11。在仓库根目录运行 PowerShell；以下命令直接调用虚拟环境解释器，无需修改脚本执行策略：

```powershell
git clone git@github.com:Small-NengNeng/starmatch_vis_tools.git
cd starmatch_vis_tools
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m tools.generate_demo
.\.venv\Scripts\python.exe star_web_app.py
```

如果没有 `py` 启动器，可使用已安装的 Python 3.11 完整路径替换 `py -3.11`。打开 <http://127.0.0.1:8765>，点击“查询并绘制”，默认应出现 **169 颗合成恒星**。按 Ctrl+C 停止服务。

演示默认值：RA=90°、DEC=0°、1024×1024 像素、像素张角 0.0098°、搜索半径 10°、星等上限 15。后端、页面和 `user_params.example.json` 使用相同默认目录：

```text
local_data/starcatalogs/simplified/demo/res5/mag15.0/epoch2000.0/
```

安装依赖需要联网；生成演示和查询已准备的星表均可离线运行。重新生成演示会覆盖该 demo 目录的瓦片。

## 使用自己的星表

页面中的 `catalog_path` 可填写绝对路径，或相对程序目录的路径。支持本项目的矩形 CSV 瓦片格式；不能直接使用新版 STARQUERY 的 HEALPix / Parquet 数据。数据来源、格式、下载和构建命令见 [数据准备](docs/data.md)。

例如，下载 Hipparcos 数据并构建瓦片：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-download.txt
.\.venv\Scripts\python.exe -m tools.get8star_json --catalog I/239/hip_main --max-magnitude 15 --output stardb_download/hip.json
.\.venv\Scripts\python.exe -m tools.build_starcat --input stardb_download/hip.json --name hip --max-magnitude 15
```

将构建工具打印的目录填入页面。星等阈值 15 只是过滤条件，不会让原星表变成完整的 15 等星表。不同星表的星等波段可能不同，使用者需要核对数据来源。

统计非空瓦片的坐标范围：

```powershell
.\.venv\Scripts\python.exe -m tools.catalog_stats --summary
```

默认统计合成演示，也可以用 `--dir` 指定其他星表。所有数据工具可通过 `python -m tools.<模块名> --help` 查看参数。

## 参数与接口

- RA/DEC、旋转角和像素张角单位为度；平移量单位为像素。查询结果按距中心的投影距离排序，`max_count` 留空表示不限数量。
- 搜索半径必须大于相机对角线张角的一半。投影保留原工具的局部近似，不是高精度 WCS 求解。
- 服务默认只监听 `127.0.0.1:8765`，用于本机操作。可用 `--host`、`--port` 指定监听参数。
- `GET /` 返回页面，`GET /healthz` 返回健康状态；`GET/POST /api/params` 读写参数，`POST /api/query` 查询。查询请求字段见参数示例，接口保持原格式。
- 最近使用的参数保存在 `user_params.json` 和浏览器本地存储中。它们不随仓库分发；需要恢复演示时，将示例参数复制为 `user_params.json` 并刷新页面。
- 数据被当前进程缓存；修改已有瓦片后请重启服务。

## 验证与打包

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试使用临时合成数据，不依赖真实星表或联网。Windows 打包步骤见 [打包说明](docs/packaging.md)。依赖按本项目直接使用的包列出，不包含整套开发机环境；可选的 `healpy` 索引功能不在本项目演示流程内。

## 发布范围与许可

本仓库包含网页、服务、数据准备工具和本地适配的查询库；不包含匹配实验、星点提取库、调试工具、旧 Git 历史或本机数据。`.gitignore` 忽略已知数据目录、环境、运行参数和构建产物。自定义数据目录请放在 `local_data/` 内或自行追加忽略规则。

自写代码采用 [MIT](LICENSE)，第三方代码与作者说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。真实星表由使用者另行获取，并遵守其来源要求。
