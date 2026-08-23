# VeryHard carrier 严格认证：当前短交接

更新时间：2026-08-22

## 固定攻坚顺序

1. Zerg Macro：最近5局至少3胜且3连胜
2. Zerg Air：最近5局至少3胜且3连胜
3. Terran Air：最近5局至少3胜且3连胜
4. Zerg Timing：稳定3连胜

Terran Macro 已完成严格认证：O414b/O415b/O416b 三连胜。

## 当前状态

- 分支：`develop`
- 最新闭环提交：`e51b179 o433 腐化四条即六门虚空转换`
- 工作区应保持clean后才能开新局。
- 当前主目标：继续 Zerg Macro；最近5局0胜5负，连胜0。
- O433：Defeat 953.6s，已完成日志/state/录像尸检、3项优化、全量测试、
  battle-log、commit+push。
- 最新测试基线：932 passed, 1 skipped；生产模块import smoke通过。

## O433 后的实机待验收项

1. 腐化信用达到4即把Gateway目标从4提高到6。
2. 腐化信用达到4即开始补VOIDRAY，最多4艘。
3. 4艘虚空成型前暂停新TEMPEST/CARRIER订单。
4. 第一批4-7腐化出现时应比O433更早完成反制转换。

## 每个有效样本的不可跳过硬门

1. `scripts/autopsy_summary.py`
2. state关键帧聚合
3. `scripts/replay_bases.py`
4. 至少3项互相区分、有数据依据的优化实际落地
5. 对应纯函数/单测
6. py_compile、完整`pytest tests -q`、import smoke
7. 更新`docs/battle-log.md`
8. commit并push `develop`
9. 以上完成后才可启动下一局

## token降耗执行规约

- 新阶段优先从本文件恢复，不读取battle-log大段尾部。
- state只输出8-12个关键时间点和所需字段，不列全量文件。
- 一次shell调用合并autopsy、录像与关键帧聚合。
- 定向测试、全量测试、import smoke各自合并，成功输出控制在1,000 token内。
- 对局监控尽量由单个本地脚本汇总，只在结果或关键异常时返回模型。
- 不重复打印完整git diff；只看`--stat`和相关hunk。
- 每个种族/风格完成后开启新Codex会话，继续引用本文件。

