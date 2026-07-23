# 踩过的坑（2026-07-18 ~ 07-21 实战全集）

> 从「代码审查 → P0 配置化 → 自调优回路 → 晋升矩阵 → pivot 迭代」整个周期里
> 真实踩过的坑，按类别归档。每条都付了学费，新会话别再交一遍。
> 运营向速查也见根目录 `CLAUDE.md`「约束 / 踩过的坑」。

## A. bot / ares 框架层

1. **warpgate 必须自己变形**。ares `SpawnController.execute` 在 WARPGATERESEARCH 完成后
   只要还有就绪空闲 gateway 就 `return False` 停产等变形，而 vendored ares 全框架没有
   变形行为——不下 `MORPH_WARPGATE` 就永久停产（stalker 0-10 的根因，
   解法 `production_manager._morph_gateways`）。
2. **多兵种 SpawnController 必开 freeflow**。配比是上限不是目标——精确配比点全兵种都
   ≥ 目标 → 全停产（配比死锁）。且 freeflow 下**首优先兵种若永远可负担会饿死其他兵种**
   （zealot p0 → 全程 0 追猎）。单兵种流派靠 `over_produce_on_low_tech` 豁免。
3. **词表名 .upper() 必须 = 引擎枚举名**。`build=twilight` → "TWILIGHT" 不存在
   （真身 TWILIGHTCOUNCIL）→ 命令静默失效。别名表必须把词表名映射到真枚举名。
4. **ares `BuildStructure` 不查 `can_afford`** → 农民到点干等不采矿。bot 层加守卫，
   不改框架。
5. **spawn 比例和必须 ≈ 1.0**（SpawnController 有 assert）；flows.yml 和
   army_composition.yml 同一约束，加载时各自校验。
6. **HonorgroundsLE 让 ares PlacementManager 开局即崩**（主矿路口摆点 IndexError）。
   bench 随机图池已排除（`_MAP_EXCLUDE`）。

## B. 环境 / 系统层

7. **本机代理 env 毒化 SC2 本地连接**（.zshrc 的 HTTP(S)_PROXY/ALL_PROXY）——
   bench 起子进程必须全剥 + `NO_PROXY=127.0.0.1,localhost`。
8. **SC2 补丁日首发失败**：当天补丁后二进制能起进程但不开 websocket、无窗口、
   静默退出 → Battle.net「扫描和修复」，别怀疑 bot。
9. **headless websocket 超时**（SC2 冷启动慢）→ runner 串行 + 失败重试一次，
   别上来就并行猛开。
10. **macOS 会恢复 App 上次的全屏状态**——想窗口化必须每局显式
    `AXFullScreen=false`，不能只"不设 true"。
11. **macOS 自带 bash 3.2**，`${var,,}` 小写展开不支持 → 用 `tr`。
12. **本机任何 python 都没有 pyobjc/Quartz**——合成输入只能走
    `osascript System Events click at`（底层也是 CGEventPost）。

## C. 进程 / 对局管理层

13. **TaskStop 杀任务不杀子进程** → SC2 孤儿黑屏占窗口/占内存。
    清理要看进程树（pgrep 时间戳，杀孤儿不杀车道）。
14. **SC2 多实例前先清场**：旧实例会和新实例互踢（单实例握手），
    `pkill -9 -x SC2` 再测。
15. **多车道共享 `~/agent-rts-steer/state.json`** 互相覆盖——
    按局取数用 `STEER_RECORD=<game_dir>` 的分目录快照，别读共享 live 文件。

## D. 交互 / UI 层

16. **bot 局小地图点击"失灵"四重因**：①窗口非键窗时点击被当"激活"吞掉；
    ②AI 投降弹窗是模态框挡全部输入；③全速模拟下离散点击被间歇丢弃；
    ④车道新局开窗每几分钟抢一次键窗。钉住焦点后全程好使。
    解法：`sc2watch`（钉前台）/ `sc2cam`（合成点击切镜头）。
17. **AI 投降要「接受」才终局**，且分两种：打 gg 聊天（bot 可检测、bench 自动点 Yes）
    和**静默弹窗**（接口探不到，只能手动点/图像识别）。
18. **合成点击前必须先显窗**——窗口隐藏时点击落在背后的桌面/终端上，白点。

## E. 实验设计层

19. **冻结测试会挡迭代**：已验证流派（tempest）的 shipped 测试冻结防手滑；
    迭代中的流派（stalker）别冻值，只测结构。
20. **一局不算证据**：胜率门槛按二项分布设计（best-of-3、N=10 ≥7、N=20 ≥14），
    固定地图+种族+风格，重打一轮再判相克。
21. **迭代中改代码会污染在跑系列**——bench 每局新起子进程，改动即时生效。
    要么等系列完，要么接受并在报告里标边界。
22. **长跑矩阵日志会写爆磁盘**——promotion 18h 能写出 25GB+（bot 每帧 debug）。
    后台任务输出必须重定向（防 16MiB 杀），且管道接 `bench/logroll.py` 只留尾部 20MB：
    `... 2>&1 | python3 bench/logroll.py bench/promo.log 20971520`。
    矩阵本身不逐局消费日志，尾部足够撞墙归因。
23. **状态文件必须原子写**——`promotion.json` 直接 `write_text` 时车道被 kill 会留下
    0 字节/半个 JSON，下次启动 `json.loads` 崩。修法：写 `.tmp` 再 `replace()`；
    `_load_state` 容忍损坏返回 `{}`——逐局 summary 在 `bench/<tag>/` 下，矩阵历史无损重放。
