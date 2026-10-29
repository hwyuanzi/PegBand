# 增强版验证结果

日期：2026-10-29。官方引擎基线：`4361337`。当前提交为 [submission/bot.cpp](submission/bot.cpp)，C++17 标准库，无额外文件或第三方依赖。

固定源码的主矩阵共 **21 个 pairing / 42 局**，两局总分 **19 胜、2 负**。每个 pairing 交换先后手，各一局；胜负按 architect 指定的两局积分总和计算。所有主矩阵对局无本 bot 非法动作、崩溃、协议错误或超时；最长整局思考 **56.38 秒**，限额为 120 秒。

旧版和旋转、镜像变体是本地强对手，不是其他同学的私有参赛 bot。败局也完整保留，不能将这些结果解释为对未知 bot 的全胜保证。

## 与首次提交旧版直接对战

| N / k / r | 对手 | 本 bot 先手 | 本 bot 后手 | 两局总分 | 分差 |
|---|---|---:|---:|---:|---:|
| 10 / 5 / 5 | Aegis v1 | 65–68 | 69–62 | 134–130 | +4 |
| 10 / 5 / 1 | Aegis v1 | 19–22 | 50–25 | 69–47 | +22 |
| 20 / 8 / 6 | Aegis v1 | 247–251 | 284–263 | 531–514 | +17 |
| 20 / 8 / 1 | Aegis v1 | 83–109 | 144–95 | 227–204 | +23 |
| 50 / 20 / 20 | Aegis v1 | 2255–2351 | 2345–2270 | 4600–4621 | -21 |
| 50 / 20 / 1 | Aegis v1 | 420–517 | 494–297 | 914–814 | +100 |

[完整报告与源码指纹](results/upgrade-v2/final-selfplay/report.json)；同目录保存每场 results.json 和 replay.html。

## 旋转、镜像强对手

| N / k / r | 对手 | 本 bot 先手 | 本 bot 后手 | 两局总分 | 分差 |
|---|---|---:|---:|---:|---:|
| 10 / 5 / 5 | Aegis v1 rotated | 62–68 | 69–62 | 131–130 | +1 |
| 10 / 5 / 5 | Aegis v1 reflected | 69–73 | 61–51 | 130–124 | +6 |
| 20 / 8 / 6 | Aegis v1 rotated | 258–278 | 317–313 | 575–591 | -16 |
| 20 / 8 / 6 | Aegis v1 reflected | 286–276 | 274–264 | 560–540 | +20 |

[完整报告与源码指纹](results/upgrade-v2/final-symmetry/report.json)；同目录保存每场 results.json 和 replay.html。

## 封锁型 Defender 对手

| N / k / r | 对手 | 本 bot 先手 | 本 bot 后手 | 两局总分 | 分差 |
|---|---|---:|---:|---:|---:|
| 10 / 5 / 5 | Defender | 59–54 | 59–47 | 118–101 | +17 |
| 20 / 8 / 6 | Defender | 251–247 | 316–229 | 567–476 | +91 |
| 20 / 8 / 1 | Defender | 147–108 | 136–84 | 283–192 | +91 |
| 50 / 20 / 20 | Defender | 2252–2330 | 2398–2192 | 4650–4522 | +128 |
| 50 / 20 / 1 | Defender | 760–538 | 744–315 | 1504–853 | +651 |

[完整报告与源码指纹](results/upgrade-v2/final-defender/report.json)；同目录保存每场 results.json 和 replay.html。

## 官方样例对手

| N / k / r | 对手 | 本 bot 先手 | 本 bot 后手 | 两局总分 | 分差 |
|---|---|---:|---:|---:|---:|
| 10 / 5 / 5 | Spread (Python) | 78–28 | 81–23 | 159–51 | +108 |
| 10 / 5 / 5 | Greedy (Python) | 85–26 | 82–49 | 167–75 | +92 |
| 10 / 5 / 5 | Random (Python) | 82–17 | 76–15 | 158–32 | +126 |
| 20 / 8 / 6 | Spread (Python) | 310–63 | 354–132 | 664–195 | +469 |
| 20 / 8 / 6 | Greedy (Python) | 303–148 | 350–141 | 653–289 | +364 |
| 20 / 8 / 6 | Random (Python) | 307–77 | 325–63 | 632–140 | +492 |

[完整报告与源码指纹](results/upgrade-v2/final-official/report.json)；同目录保存每场 results.json 和 replay.html。

## 本轮保留的改进

- 修复末手候选剪枝漏掉更优位置的问题；一例 20×20、8 peg、6 band 的终局分差从 98 提升至 100，独立穷举核验。
- 小棋盘（N≤12、k≤6）最后四次落点枚举全部空格做 minimax，先用短搜索取得后备选择；时限内保留已经完全评估的较优根分支。该搜索有时限，不承诺所有实际局面均完成全树。
- 中等棋盘扩大末手搜索；大棋盘末手候选由 48 扩至 256。将额外思考集中到可直接计算 band 得分的终局，而不是一律增加早期深度。
- 复用落点和搜索界限缓存，减少三角形分配，并用精确按行覆盖计算替代逐格裁剪。
- 多 band 大棋盘保留 v1 落点策略直到 Green 末手，Blue 末手使用增强规划。全程使用新搜索、加深搜索、固定中心开局等实验未显示普遍收益，因此未采用。

普通落点上限 4 秒，增强末手上限 18 秒，小棋盘倒数第二手上限 12 秒；另检查剩余整局预算。20 peg 配置的这些时间上限加 band 规划不超过 99 秒（几何预处理、系统调度仍有额外开销）。band 规划只执行一次。

## 正确性与单文件交付

- **51 项 unittest 通过**：包括 805 个 band 几何案例、1,300 个落点栅格案例，以及独立穷举的 band 最优性检查。
- 新增两个先手最后落点的完整对手回应回归、一个中棋盘末手漏选回归，以及五个小棋盘最后四步全游戏树核验。
- 最大 50×50、20 peg、20 band 的合法性和协议测试通过。
- 单文件在只含 bot.cpp 的临时目录中用 `c++ -std=c++17 -O2 -Wall -Wextra -pedantic bot.cpp -o bot` 编译通过，无编译诊断。
- 预处理后的非空源代码与分文件版本完全一致；ZIP 只含 `haowen/bot.cpp`，其字节与单文件相同。
- 隔离单文件对 Greedy：先手 85–26，后手 82–49；无非法动作或错误。[单文件实战报告](results/upgrade-v2/final-single-cpp/report.json)。

提交文件 SHA-256：

`7819208444270fab6aac81a64af1e69ff2fdae5f2b81742d85747d61ad00185b`

[汇总核验和源码指纹](results/upgrade-v2/final-validation.json)。测试平台为本机 macOS ARM64；墙上时间限时搜索会随 CPU 和并发负载改变完成深度及落点。单 peg 的 pairing 必然平局，不能保证任意参数、任意对手均获胜。课程网站需要 NYU 登录；规则依据提供的邮件和官方引擎。

## 复现

```sh
python3 -m unittest discover -s tests -t .
python3 tools/package_bot.py
python3 tools/benchmark.py --registry tools/opponents/upgrade-registry.json --opponent "Aegis v1" --params 20,8,6
python3 tools/benchmark.py --registry tools/opponents/upgrade-registry.json --opponent Defender --params 50,20,20
python3 tools/benchmark.py --params 10,5,5 --params 20,8,6
```

[首次提交的历史测试](BENCHMARKS-v1.md)。本轮筛选过程的试验位于本机 results/research/upgrade-v2/，未混入以上固定源码主矩阵。
