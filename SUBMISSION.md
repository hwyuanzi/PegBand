# 提交给 architect

附件：`submission/haowen-pegband.zip`。解压后是完整的 `haowen/` bot 文件夹。

邮件正文可以直接使用：

> Hi Keefer,
>
> Attached is my complete PegBand bot folder.
>
> Bot name: Haowen Aegis (the dashboard discovers the folder as `haowen`).
> Language: C++17, standard library only.
> Build: Python 3.8+ and a C++17 compiler such as Apple Clang. No packages to install.
> Place the entire `haowen` folder under `bots/` and press Rescan. The official
> referee automatically runs `python3 build.py`. Alternatively, compile with
> `c++ -std=c++17 -O2 bot.cpp -o bot`, then run `./bot`.
>
> The README in the folder contains the setup details.
>
> Best,
> Haowen

尚未发送邮件。压缩包仅包含本 bot 的源码和说明，不包含官方引擎、测试对手或本机二进制。

本地运行：在项目根目录执行 `python3 start.py`，然后打开
<http://127.0.0.1:8092>，点击 Rescan，选择 `haowen`。

回归测试：

```sh
python3 -m unittest discover -s tests -t .
python3 tools/benchmark.py --params 10,5,5
```
