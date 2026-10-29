# 提交给 architect

直接提交 **`submission/bot.cpp`** 即可：全部策略代码已合并在内，只依赖 C++ 标准库。

如果需要文件夹压缩包，提交 `submission/haowen-single-cpp.zip`，解压后只有
`haowen/bot.cpp`。把 `haowen/` 放入官方架构的 `bots/` 后点击 Rescan，
裁判会用默认 C++17 编译命令自动编译，无需 `build.py`。

邮件正文可以直接使用：

> Hi Keefer,
>
> Attached is my single-file PegBand bot, bot.cpp.
>
> Bot name: Haowen Aegis (the dashboard discovers the folder as `haowen`).
> Language: C++17, standard library only.
> Build: a C++17 compiler such as Apple Clang. No packages or extra files needed.
> Place bot.cpp in bots/haowen/ and press Rescan. The official referee compiles
> it automatically. To compile manually, run
> `c++ -std=c++17 -O2 bot.cpp -o bot`, then run `./bot`.
>
> Best,
> Haowen

尚未发送邮件。单文件已包含全部策略实现，不需要额外发送 `.h` 文件。
仓库内 `bots/haowen/` 保留便于维护的分文件版本，策略相同。
请使用重新生成的最新单文件；旧文件不会自动获得本轮终局搜索改进。

重新生成单文件：`python3 tools/package_bot.py`。

本地运行：在项目根目录执行 `python3 start.py`，然后打开
<http://127.0.0.1:8092>，点击 Rescan，选择 `haowen`。

回归测试：

```sh
python3 -m unittest discover -s tests -t .
python3 tools/benchmark.py --params 10,5,5
```
