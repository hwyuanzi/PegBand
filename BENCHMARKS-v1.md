> 历史记录：首次提交的 v1（d6fff01），不是当前增强版的测试结果。

# 验证结果

测试日期：2026-10-29。官方引擎基线：`4361337`。
所有比分均为 **Haowen Aegis 的分数在前**；每个 pairing 包括绿方、蓝方各一局。
下面使用提交源码的默认搜索预算及官方每局 120 秒计时。

## 官方示例对手

| N / k / r | 对手 | Aegis 先手 | Aegis 后手 | Aegis 最长整局思考 / 秒 |
|---|---|---:|---:|---:|
| 10 / 5 / 5 | Spread (Python) | 78–28 | 72–38 | 6.15 |
| 10 / 5 / 5 | Greedy (Python) | 80–25 | 85–56 | 7.20 |
| 10 / 5 / 5 | Random (Python) | 73–16 | 76–15 | 6.43 |
| 20 / 8 / 6 | Spread (Python) | 302–59 | 330–120 | 19.49 |
| 20 / 8 / 6 | Greedy (Python) | 357–119 | 376–112 | 17.96 |
| 20 / 8 / 6 | Random (Python) | 325–81 | 325–63 | 22.64 |
| 20 / 8 / 1 | Spread (Python) | 134–66 | 177–52 | 21.64 |
| 20 / 8 / 1 | Greedy (Python) | 213–67 | 167–50 | 21.74 |
| 20 / 8 / 1 | Random (Python) | 165–11 | 162–12 | 21.43 |
| 50 / 20 / 20 | Random (Python) | 2417–458 | 2373–485 | 51.45 |

以上 20 局全部获胜；本 bot 没有非法落点、非法 band、协议错误或超时。
Random 自身可能输出被拒绝的 band；这里没有把它的非法动作解释为本 bot 的优化能力。
完整对局、实际用时和源码 SHA-256 在 [results/final-official](results/final-official/) 下。

## 独立封锁型测试对手

Defender 是本地单独实现的测试对手，并非其他同学的私有参赛 bot。
它采用中心开局、偏重封锁的落点策略，并共享本 bot 的 band 规划器。
对战结果和回放见 [最终 Defender 测试](results/research/final-defender-matrix/report.json)。

| N / k / r | Aegis 先手 | Aegis 后手 | Aegis 最长整局思考 / 秒 |
|---|---:|---:|---:|
| 10 / 5 / 5 | 68–59 | 80–57 | 7.87 |
| 20 / 8 / 6 | 290–255 | 298–214 | 18.53 |
| 20 / 8 / 1 | 156–107 | 161–95 | 19.53 |
| 50 / 20 / 20 | 2390–2265 | 2398–2193 | 51.59 |

这 8 局全部获胜，本 bot 无非法动作、崩溃或超时。

另外完成最大 peg 数、仅一条 band 的压力测试：`N=50,k=20,r=1`。
对 Defender 先手 **927–392**、后手 **737–446**；整局思考分别 **57.22 秒**、
**55.47 秒**，双方无非法动作或错误。见 [单 band 最大局面报告](results/final-max-r1/report.json)
与 [回放](results/final-max-r1/match/replay.html)。

合计主测试参数（k≥3）：官方样例 20 局、Defender 10 局，全部获胜。
这不包含用于调试的旧版本对局，也没有把必然平局的单 peg 配置算入胜局。



## 正确性与交付

- `python3 -m unittest discover -s tests -t .`：48 项测试通过。
- 包含 805 个 band 几何对照案例、1,300 个落点评价几何对照案例，以及小局面穷举最优性对照。
- 20 个小棋盘末手局面逐格穷举核对真实终局分差；修复候选筛选漏掉最佳落点的问题后全部通过。
- 最大 50×50、20 peg、20 band 的协议与合法性检查通过。
- 单 peg 的 pairing 必然 2–2；10×10、两 peg 对 Greedy 的 pairing 为 36–36。此类平局没有计作上表胜局。
- 提交 ZIP 已在隔离临时目录解压，成功独立编译并完成 start/peg/band 协议检查。
- 主程序为 C++17 标准库；编译助手为 Python 3.8+；无第三方依赖。

测试平台是本机 macOS ARM64。比赛目标为 architect 邮件说明的 M2 / 8GB。
落点搜索按墙上时间限时，机器速度及并发负载会影响完成的搜索深度和具体落点。
这些结果证明了已测试对手上的表现，不构成对未知参赛 bot 的胜率保证。
课程网站需要 NYU 登录，未读取到其受保护内容；规则依据你提供的邮件和官方引擎。

## 复现

```sh
python3 -m unittest discover -s tests -t .
python3 tools/benchmark.py --params 10,5,5 --params 20,8,6 --params 20,8,1
python3 tools/benchmark.py --registry tools/opponents/registry.json --opponent Defender --params 20,8,6
```
