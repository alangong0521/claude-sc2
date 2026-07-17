# Changelog — code-agent-sc2

语义化版本。An LLM chief-of-staff steers a self-driving ares-sc2 bot in real time.

## [Unreleased] — open-source readiness

面向对外开源的一次整备（无对局行为改动）/ Open-source prep, no gameplay changes.

- **Rebrand → `code-agent-sc2`**（官方方向定为神族 Protoss；受众中英双语）。
- **Licensing / attribution**：新增项目级 `LICENSE`(MIT) 与 `NOTICE`（保留 ares-sc2 /
  ares-random-example / python-sc2 的上游署名，声明未分发参考 bot）。
- **Docs**：全新双语 README（默认中文 `README.md` / 英文 `README_en.md`）——项目定位、架构图、跨平台
  安装/运行、「用任意 LLM 指挥」说明、杠杆词表、致谢与许可。新增 `CONTRIBUTING.md`、
  issue/PR 模板。
- **参谋长技能随仓库分发**：`.claude/skills/sc2-claude/`（路径改为相对仓库根）。
- **词表单一真相源**：真正落地 `bot/steer_vocab.py`，`steer.py` / `steer_cli.py` 都从它
  导入（此前两处各抄一份、且 README 声称的该文件并不存在）。
- **仓库卫生**：`refs/`（15 个他人 bot）与 `_archive_*` 改为不跟踪（仅本地留存，不再分发）；
  移除 5 个重构后遗留、已删但仍被跟踪的死文件（`bot/consts.py`、`bot/tools/*` 等）。
- **CI**：新增轻量 `ci.yml`——语法编译 + 纯 Python 跑通 steer CLI/词表（不需 SC2/ares）。
- **Windows 支持（静态验证级）**：`run.py` 按 OS 自动选 `MAPS_PATH` 默认值（win/mac/linux）；
  README 增补 Windows 一节（Python 3.11/3.12、win_amd64 wheel 免编译、PowerShell 跑法、
  `taskkill /F /IM SC2_x64.exe` 收尾）；sc2-claude 技能补齐 macOS/Linux 与 Windows 双平台的
  进程结束命令；`smoke.py` 路径提示改为平台中性。尚未在 Windows 实机端到端验证。

> 备注：Poetry 包名 `name` 有意保留原模板值——虚拟环境按它定位，改名会让所有人的已装环境脱钩。品牌名只体现在文档里。

## v0.1.0 — 2026-06-28

第一个经验证、可运行的版本。从 `spike/sc2` 晋升而来。

**机制(五层)**:SC2 免费客户端 ← python-sc2 ← ares 自动驾驶 bot ← 两个 JSON 文件信道(`~/agent-rts-steer/`)← 受约束的 5 字段杠杆 ← Claude(军师,读局势 + 下高层命令,不碰微操)。

**已验证**
- Stage 0:原生 Mac 客户端能被 python-sc2 拉起、载图、打完一局(`smoke.py`)。
- Stage 1:ares bot 默认(无命令)即胜 Hard 内置 AI(`ares-bot/`)。
- Stage 2:实时 steer 闭环——Claude 读 `state.json` → `steer_cli.py set` 下命令 → bot 接住执行 → 实战赢下一局(vs Hard Protoss)。

**组成**
- `smoke.py` — 启动探针(裸 burnysc2,Python 3.13)。
- `ares-bot/` — 带教 bot + steer 层(Python 3.11 + poetry,ares-sc2 v3.9.6 vendored)。
  - `bot/main.py`(ares 子类 + steer 接缝)、`bot/steer.py`(JSON IO + 兵种预设)、
    `bot/steer_vocab.py`(共享词表)、`steer_cli.py`(指挥 CLI)、`spike_config.py`、`run.py`。

**已知限制(→ 下一版)**
1. 暴兵被风筝(微操打最近敌人,不强突骚扰兵)。
2. 矿溢出(SpawnController 只用现有产能,单基地花不掉钱)→ 需产能/扩张杠杆。
3. state 只含当前可见单位(战争迷雾),缺侦察记忆。
4. Zerg 开局 build 卡住(人口卡 12、不出王虫)。

**迁移备注**:从旧路径移来后,ares-bot 的 poetry 虚拟环境(按项目路径哈希定位)已脱钩,首次运行前 `cd ares-bot && poetry install` 重新关联一次(依赖已缓存)。
