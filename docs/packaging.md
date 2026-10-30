# Windows 打包（不包含星表）

在 Windows、Python 3.11 的隔离环境中，从仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm star_web_app.spec
```

生成目录为 `dist/star_web_app/`。需要分发整个目录，包括 `_internal/`；不能只复制 exe。页面文件随程序打包，星表、个人参数和实验数据均不打入包中。

先运行 `python -m tools.generate_demo`，再将生成的 `local_data/` 复制到 exe 同级目录：

```text
dist/star_web_app/
  star_web_app.exe
  _internal/
  local_data/starcatalogs/simplified/demo/res5/mag15.0/epoch2000.0/...
```

启动 exe 后访问 <http://127.0.0.1:8765>。真实星表也可放在其他目录，通过页面指定。`user_params.json` 会生成在 exe 旁，因此该目录需要写权限。不要将个人参数文件放入公开分发包。

`build/`、`dist/` 和 exe 已被忽略。本次仓库只发布源码；将来另行分发可执行包时，还需随包保留所含第三方依赖的许可证。
