"""判据 import 完整性检查（O121/O126/O128 三次 NameError 事故后入档）。

用法：cd ares-bot && poetry run python scripts/check_judge_imports.py
原理：bot 层新判据定义在 production_plans.py，manager/main 侧忘 import 时
import 级编译检查抓不住（NameError 在函数体内，运行时才炸）。本脚本用 AST
对比「用到的判据名」与「import 清单」，把这类事故挡在 bench 之前。
"""

import ast
import sys

FILES = [
    "bot/managers/production_manager.py",
    "bot/main.py",
    "bot/managers/combat_manager.py",
]


def main() -> int:
    plans = ast.parse(open("bot/production_plans.py").read())
    plan_defs = {
        n.name for n in ast.walk(plans) if isinstance(n, ast.FunctionDef)
    }
    bad = False
    for path in FILES:
        tree = ast.parse(open(path).read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported.add(alias.asname or alias.name)
        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        missing = sorted((used & plan_defs) - imported)
        if missing:
            bad = True
            print(f"{path}: MISSING {missing}")
        else:
            print(f"{path}: OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
