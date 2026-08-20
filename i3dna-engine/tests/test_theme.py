# -*- coding: utf-8 -*-
"""主题判型（形状定律 8-21·工单1号）：消息类型文件声明 主题: ＝**目录即
类型**——判型两级：①文件所在目录命中主题模式 → 该类型（不看文件名，
乱名也是单）；②未命中 → 老路文件名剥 __ 段寻种。零主题声明＝老行为
原样（向后兼容律）。draft 案卷材料门同步：落进主题目录＝伪造单据，拒。
判据=_type_file 返回值+磁盘与退出码（97号：断言与账）。"""
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "i3dna_engine.py")

TASK = """---
i3dna: 微任务
执行者: 人
输入:
  - "实例/甲/{案卷号}/审批单/乱名zzz.md"
  - "实例/甲/{案卷号}/审批单/__批注.md"
  - "实例/甲/{案卷号}/别处/审批单.md"
  - "实例/甲/{案卷号}/别处/乱名qqq.md"
产物:
  - "{实例}/出.md"
---
吃单（第一张走主题目录，后两张走老路对照）。
"""

TYPE_WITH_THEME = """---
i3dna: 消息
主题: "实例/甲/{案卷号}/审批单"
键:
  - 申请人
---
审批单种（目录即类型）。
"""

TYPE_NO_THEME = """---
i3dna: 消息
键:
  - 申请人
---
审批单种（未声明主题——老行为对照）。
"""


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _tree(tmp_path, theme=True):
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n范畴: 过程\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/消息/审批单.md",
        TYPE_WITH_THEME if theme else TYPE_NO_THEME)
    _mk(r, "域/x域/类/甲/方法/办/任务.md", TASK)
    _mk(r, "实例/甲/c1/申请.md", "---\n域名: d9\n---\n申请。\n")
    _mk(r, "实例/甲/c1/审批单/乱名zzz.md",
        "---\n申请人: 张三\n---\n第一张单。\n")
    return r


def _load():
    spec = importlib.util.spec_from_file_location("i3dna_engine_t", ENGINE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _rows_by_name(task):
    return {os.path.basename(x["pname"]): x for x in task["rows"]
            if x["kind"] == "输入"}


def test_主题命中_目录内乱名判该类型(tmp_path):
    """验收②：目录即类型——主题目录里任意文件名（含乱名）判为该类型；
    __/点前缀件豁免（账不进账老钉，§8.12 同源）。"""
    eng = _load()
    r = _tree(tmp_path, theme=True)
    task = eng.load_task(os.path.join(r, "域/x域/类/甲/方法/办"),
                         r, case="c1")
    rows = _rows_by_name(task)
    row = rows["乱名zzz.md"]
    tf = eng._type_file(task, row, "消息")
    assert tf is not None and tf.endswith(os.path.join("消息", "审批单.md")), tf
    assert eng.is_message(task, row), "主题命中＝消息（不看文件名）"
    assert eng._type_file(task, rows["__批注.md"], "消息") is None, \
        "__ 前缀件豁免主题判型——主题目录里的账不是单据"


def test_主题未命中_文件名仍走老路(tmp_path):
    """验收③：主题外目录不参与判型——名字命中类型走②级寻种，乱名落空。"""
    eng = _load()
    r = _tree(tmp_path, theme=True)
    task = eng.load_task(os.path.join(r, "域/x域/类/甲/方法/办"),
                         r, case="c1")
    rows = _rows_by_name(task)
    tf = eng._type_file(task, rows["审批单.md"], "消息")
    assert tf is not None and tf.endswith(os.path.join("消息", "审批单.md")), \
        "别处/审批单.md 不在主题目录——名字命中级命中"
    assert eng._type_file(task, rows["乱名qqq.md"], "消息") is None, \
        "主题外乱名＝无类型（老行为）"


def test_零主题声明_老行为逐字节兼容(tmp_path):
    """验收①（判型面）：不声明 主题: → 乱名一律寻不到种（＝改动前）。"""
    eng = _load()
    r = _tree(tmp_path, theme=False)
    task = eng.load_task(os.path.join(r, "域/x域/类/甲/方法/办"),
                         r, case="c1")
    rows = _rows_by_name(task)
    assert eng._type_file(task, rows["乱名zzz.md"], "消息") is None
    assert not eng.is_message(task, rows["乱名zzz.md"])
    assert eng._type_file(task, rows["审批单.md"], "消息") is not None, \
        "名字命中级不受影响"


def _draft(r, payload):
    return subprocess.run(
        [sys.executable, ENGINE, "draft",
         os.path.join(r, "域/x域/类/甲/方法/办"), "--root", r,
         "--case", "c1"],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True, text=True, timeout=60)


def test_draft_落进主题目录_乱名也是伪单_拒(tmp_path):
    """验收②（draft 门）：案卷材料落进主题目录＝伪造单据（目录即类型），
    乱名也拒——工单108 F3 的主题推广。"""
    r = _tree(tmp_path, theme=True)
    p = _draft(r, [{"路径": "审批单/完全乱的名字.md", "内容": "伪单\n"}])
    assert p.returncode != 0
    assert "单据不是材料" in (p.stdout + p.stderr)
    assert "主题" in (p.stdout + p.stderr)
    assert not os.path.exists(
        os.path.join(r, "实例/甲/c1/审批单/完全乱的名字.md")), "零副作用"


def test_draft_零主题_同路径是合法材料(tmp_path):
    """验收①（draft 门）：无主题声明时同一路径＝案卷材料，照落（兼容）。"""
    r = _tree(tmp_path, theme=False)
    p = _draft(r, [{"路径": "审批单/完全乱的名字.md", "内容": "材料\n"}])
    assert p.returncode == 0, p.stderr
    assert open(os.path.join(r, "实例/甲/c1/审批单/完全乱的名字.md"),
                encoding="utf-8").read() == "材料\n"
