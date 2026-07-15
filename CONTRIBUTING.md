# Contributing to code-agent-sc2

Thanks for your interest! / 感谢参与！Issues and PRs are welcome.

## Ground rules / 基本约定

- **Keep the vendored `ares-bot/ares-sc2/` untouched** unless you're deliberately updating the
  upstream copy. It's a bundled dependency, not our code.
  除非你有意升级上游，否则**别改 vendored 的 `ares-bot/ares-sc2/`**。
- **Don't rename the Poetry package** (`ares-bot/pyproject.toml` `name`). Poetry keys its
  virtualenv to it; renaming orphans everyone's installed env. Brand identity lives in the README.
  **别改 Poetry 的 `name`**——虚拟环境按它定位，改了会让所有人的环境脱钩。
- **Do not commit reference bots or replays.** `refs/`, `_archive_*/`, `*.SC2Replay` and `*.log`
  are gitignored on purpose. Reference bots belong to their authors and are not redistributed.
  **别提交参考 bot 或 replay**——`refs/`、`_archive_*/` 等已被 gitignore。

## The lever vocabulary / 杠杆词表

`ares-bot/bot/steer_vocab.py` is the **single source of truth** for the command vocabulary.
Both the bot (`steer.py`) and the CLI (`steer_cli.py`) import from it — add or change levers
there, in one place.
词表以 `steer_vocab.py` 为**单一真相源**，bot 侧和 CLI 都从它导入，改一处即可。

## Dev setup / 开发环境

```bash
cd ares-bot
poetry install
poetry run python steer_cli.py vocab      # quick sanity check, no game needed
```

## Before you open a PR / 提 PR 前

- Make sure `python ares-bot/steer_cli.py vocab` still runs and the modules import cleanly.
- If you touched steer levers, update **both** `README.md` (中文) and `README_en.md` vocab tables and
  the `.claude/skills/canmou/SKILL.md` command table.
  改了杠杆，请**同时**更新中英 README 的词表和参谋长技能里的命令表。
- Describe what you changed and how you tested it (a replay or a headless win/loss run helps).

## Scope

This project is about the **command layer** (LLM-in-the-loop steering), not about maximizing
ladder MMR. Bot-strength PRs are welcome, but the north star is a legible, fun command interface.
本项目关注的是**指挥层**（LLM 在环 steer），不是冲天梯分数。
