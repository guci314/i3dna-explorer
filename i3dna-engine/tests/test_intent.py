# -*- coding: utf-8 -*-
"""意图入账（101号 右键对话 S1）：fire/settle 账记「意图」=话语原文；
advance(converge) 穿透 executor+intent；lint 双读兼容（无意图旧账不比对）。
判据=账 JSON 与 lint 报告（97 号：账与断言）。"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.join(os.path.dirname(HERE), "i3dna_api.py")
LINT = os.path.join(os.path.dirname(os.path.dirname(HERE)),
                    "i3dna-lint", "i3dna_lint.py")

TASK = """---
i3dna: 微任务
输入:
  - "{实例}/申请.md"
产物:
  - "{实例}/出.md"
---
干活。
"""

STUB = """import os, re, sys
prompt = sys.stdin.read()
for p in re.findall(r"【产物→写到】(\\S+)", prompt):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("桩产物\\n")
print("完成")
"""


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _tree(tmp_path):
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n范畴: 过程\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/方法/办/任务.md", TASK)
    _mk(r, "实例/甲/c1/申请.md", "---\n键: 值\n---\n申请。\n")
    _mk(r, "桩.py", STUB)
    return r


def call(verb, root, *flags):
    return subprocess.run([sys.executable, API, verb, root, *flags],
                          capture_output=True, text=True)


def _账(root, case="c1"):
    d = json.loads(call("account", root, "--task",
                        "域/x域/类/甲/方法/办", "--case", case).stdout)
    return d["账"][0]["记录"]


def test_fire_意图入账(tmp_path):
    r = _tree(tmp_path)
    f = call("fire", r, "--task", "域/x域/类/甲/方法/办", "--case", "c1",
             "--engine", f"{sys.executable} {os.path.join(r, '桩.py')}",
             "--executor", "实例/人员/刘亦菲",
             "--intent", "把这一单出库发给广州仓")
    assert f.returncode == 0, f.stderr
    rec = _账(r)
    assert rec["意图"] == "把这一单出库发给广州仓", "话语原文须逐字入账"
    assert rec["执行者"] == "实例/人员/刘亦菲"
    assert rec["产物清单"][0]["sha256"]                    # 对账判据不受意图影响


def test_settle_意图入账(tmp_path):
    r = _tree(tmp_path)
    _mk(r, "实例/甲/c1/出.md", "产物\n")
    s = call("settle", r, "--task", "域/x域/类/甲/方法/办", "--case", "c1",
             "--executor", "实例/人员/刘亦菲", "--intent", "办结这一单")
    assert s.returncode == 0, s.stderr
    assert _账(r)["意图"] == "办结这一单"


def test_advance_穿透意图与执行者(tmp_path):
    """advance 签字（101号）：converge 点的火也盖登录主体与话语原文。"""
    r = _tree(tmp_path)
    a = call("advance", r, "--case", "c1",
             "--engine", f"{sys.executable} {os.path.join(r, '桩.py')}",
             "--executor", "实例/人员/刘亦菲", "--intent", "推进这一单")
    assert a.returncode == 0, a.stderr
    rec = _账(r)
    assert rec["状态"] == "执行"
    assert rec["执行者"] == "实例/人员/刘亦菲", "advance 须穿执行者"
    assert rec["意图"] == "推进这一单", "advance 须穿意图"


def test_旧账无意图_lint双读兼容(tmp_path):
    """无意图字段的旧账：lint 不比对不报错（账实对账只核清单 sha）。"""
    r = _tree(tmp_path)
    f = call("fire", r, "--task", "域/x域/类/甲/方法/办", "--case", "c1",
             "--engine", f"{sys.executable} {os.path.join(r, '桩.py')}")
    assert f.returncode == 0, f.stderr
    assert "意图" not in _账(r), "未传意图不写空键"
    p = subprocess.run([sys.executable, LINT, r],
                       capture_output=True, text=True)
    assert p.returncode == 0 and "干净" in (p.stdout + p.stderr), \
        "无意图旧账须 lint 干净（双读兼容：不比对缺失的意图键）"


def test_绿任务执行者主体覆盖不失守(tmp_path):
    """执行者:人 的站，--executor 传人员主体值也不得点火（声明机制值
    守卫——右键对话 8-20 验收修复：人工守卫不因主体署名被 argv 拆除）。"""
    r = str(tmp_path)
    green = TASK.replace("---\n", "---\n执行者: 人\n", 1)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n范畴: 过程\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/方法/办/任务.md", green)
    _mk(r, "实例/甲/c1/申请.md", "---\n键: 值\n---\n申请。\n")
    f = call("fire", r, "--task", "域/x域/类/甲/方法/办", "--case", "c1",
             "--engine", f"{sys.executable} {os.path.join(r, '桩.py')}",
             "--executor", "实例/人员/刘亦菲",
             "--intent", "帮我把它点了吧")
    assert f.returncode != 0, "绿任务不得被主体值代点火"
    assert "不代人点火" in (f.stdout + f.stderr)
    assert not os.path.exists(os.path.join(r, "实例/甲/c1/__账")), \
        "拒绝零副作用"


def test_案卷号注入拒(tmp_path):
    """--case 路径注入（../../x）＝响亮拒绝，不得写出树外（对话面防线）。"""
    r = _tree(tmp_path)
    _mk(r, "实例/甲/c1/出.md", "产物\n")
    s = call("settle", r, "--task", "域/x域/类/甲/方法/办",
             "--case", "../../pwned_case", "--intent", "注入")
    assert s.returncode != 0 and "不干净" in (s.stdout + s.stderr)
    assert not os.path.exists("/tmp/pwned_case")
