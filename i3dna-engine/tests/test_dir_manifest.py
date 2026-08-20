# -*- coding: utf-8 -*-
"""目录盘点单（§8.12 修复）：目录输入弧记「收盘盘点」入账——
converge 对含目录弧的任务收敛（原：声明输入未入账→重点火到 max_rounds 退3）；
目录已变可测；`__` 目录不入清单（账不进账）；lint 盘点对账同形。"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.join(os.path.dirname(HERE), "i3dna_api.py")

TASK = """---
i3dna: 微任务
输入:
  - "实例/审查/收件箱"
产物:
  - "出.md"
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


def call(verb, root, *flags):
    return subprocess.run([sys.executable, API, verb, root, *flags],
                          capture_output=True, text=True)


def _tree(tmp_path):
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/方法/办/任务.md", TASK)
    _mk(r, "实例/审查/收件箱/请求审查单__A.md", "单：A\n")
    _mk(r, "桩.py", STUB)
    return r


def test_目录弧入账_收盘盘点(tmp_path):
    r = _tree(tmp_path)
    f = call("fire", r, "--task", "域/x域/类/甲/方法/办",
             "--engine", f"{sys.executable} {os.path.join(r, '桩.py')}")
    assert f.returncode == 0, f.stderr
    d = json.loads(call("account", r).stdout)
    rec = d["账"][0]["记录"]
    ent = next(it for it in rec["输入清单"] if it.get("目录"))
    assert ent["名称"] == os.path.join("实例", "审查", "收件箱")
    assert "请求审查单__A.md" in ent["清单"], "账要说出收件箱里有哪张单"


def test_目录弧收敛_不再永不收敛(tmp_path):
    """§8.12 正主：含目录弧的任务点火后，converge 判新鲜（原每轮
    「声明输入未入账」重复点火到退3）。"""
    r = _tree(tmp_path)
    f = call("fire", r, "--task", "域/x域/类/甲/方法/办",
             "--engine", f"{sys.executable} {os.path.join(r, '桩.py')}")
    assert f.returncode == 0, f.stderr
    p = call("advance", r, "--plan")
    assert p.returncode == 0, p.stderr + p.stdout
    assert "声明输入未入账" not in p.stdout
    assert "计划点火 0 站" in p.stdout, p.stdout


def test_目录已变催火(tmp_path):
    r = _tree(tmp_path)
    f = call("fire", r, "--task", "域/x域/类/甲/方法/办",
             "--engine", f"{sys.executable} {os.path.join(r, '桩.py')}")
    assert f.returncode == 0, f.stderr
    _mk(r, "实例/审查/收件箱/请求审查单__B.md", "单：B\n")   # 新单落箱
    p = call("advance", r, "--plan")
    assert "目录已变" in p.stdout, p.stdout


def test_双下划线目录不入盘点(tmp_path):
    """"__" 前缀目录（__账/__日志）不入清单——账不能是自己的输入。"""
    r = _tree(tmp_path)
    _mk(r, "实例/审查/收件箱/__账/x.json", "{}")
    _mk(r, "实例/审查/收件箱/.隐藏/h.md", "x")
    f = call("fire", r, "--task", "域/x域/类/甲/方法/办",
             "--engine", f"{sys.executable} {os.path.join(r, '桩.py')}")
    assert f.returncode == 0, f.stderr
    d = json.loads(call("account", r).stdout)
    ent = next(it for it in d["账"][0]["记录"]["输入清单"] if it.get("目录"))
    assert "__账" not in json.dumps(ent["清单"], ensure_ascii=False)
    assert ".隐藏" not in json.dumps(ent["清单"], ensure_ascii=False)


def test_lint_盘点对账(tmp_path):
    r = _tree(tmp_path)
    f = call("fire", r, "--task", "域/x域/类/甲/方法/办",
             "--engine", f"{sys.executable} {os.path.join(r, '桩.py')}")
    assert f.returncode == 0, f.stderr
    _mk(r, "实例/审查/收件箱/请求审查单__B.md", "单：B\n")
    d = json.loads(call("lint", r).stdout)
    assert any("目录已变" in w["消息"] for w in d["警告"]), d["警告"][:3]
