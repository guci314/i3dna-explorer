# -*- coding: utf-8 -*-
"""lint ⑦ 无照手术（8-19 裁定 C 档·警告级）：女娲在场的树，手术面
（类.md/schema.md/方法/*/任务.md）须有出处——宪法时刻基线或账目产物。
五臂：无照新增／基线手改／基线删除／女娲火豁免／无女娲休眠。"""
import glob
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LINT = os.path.join(os.path.dirname(os.path.dirname(HERE)), "i3dna-lint",
                    "i3dna_lint.py")
sys.path.insert(0, os.path.dirname(LINT))

import i3dna_lint as lint   # noqa: E402

TASK = """---
i3dna: 微任务
输入:
  - "{实例}/申请.md"
产物:
  - "{实例}/出.md"
---
x
"""

NUWA_TASK = """---
i3dna: 微任务
执行者: 蓝
输入:
  - "{实例}/申请.md"
产物:
  - "域/{申请.域}/类/{申请.类名}/类.md"
---
按女娲格式立类。
"""


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _tree(tmp_path, with_baseline=True):
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/方法/办/任务.md", TASK)
    _mk(r, "域/治理域/类/女娲/类.md",
        "---\ni3dna: 类\n关系: []\n---\n# 女娲\n")
    _mk(r, "域/治理域/类/女娲/方法/立类/任务.md", NUWA_TASK)
    faces = sorted(glob.glob(os.path.join(r, "域", "*", "类", "*", "类.md"))) \
        + sorted(glob.glob(os.path.join(r, "域", "*", "类", "*", "方法", "*",
                                        "任务.md")))
    if with_baseline:
        rows = "\n".join(
            f"| {os.path.relpath(p, r)} | "
            f"{hashlib.sha256(open(p, 'rb').read()).hexdigest()} |"
            for p in faces)
        _mk(r, "域/治理域/类/女娲/知识/宪法时刻.md",
            "---\ni3dna: 知识\n---\n# 宪法时刻\n\n"
            "| 路径 | sha256 |\n|---|---|\n" + rows + "\n")
    return r


def _warns(r):
    rep = lint.Report()
    lint.lint_unlicensed_surgery(r, rep)
    return [(w, m) for w, m in rep.warnings]


def test_无照新增_警告(tmp_path):
    r = _tree(tmp_path)
    _mk(r, "域/x域/类/野类/类.md", "---\ni3dna: 类\n---\n# 野类\n")
    hits = _warns(r)
    assert any("野类" in w and "无照手术" in m for w, m in hits), hits


def test_基线面手改_警告(tmp_path):
    r = _tree(tmp_path)
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n---\n# 甲改\n")  # 直改
    assert any("手术后手改" in m for w, m in _warns(r))


def test_基线删除_警告_回收弧豁免(tmp_path):
    r = _tree(tmp_path)
    os.remove(os.path.join(r, "域/x域/类/甲/方法/办/任务.md"))
    assert any("已不在场" in m for w, m in _warns(r))
    import json
    rec = {"回收清单": [{"名称":
            os.path.join("域", "x域", "类", "甲", "方法", "办", "任务.md")}]}
    _mk(r, "实例/女娲/废/x.md", "1")
    _mk(r, "实例/女娲/废/__账/立类/__结果.json", json.dumps(rec, ensure_ascii=False))
    assert not any("已不在场" in m for w, m in _warns(r)), "回收弧销账后不应再报"


def test_女娲火产物_豁免(tmp_path):
    """正经通道：立类火的产物进账 → 手术面有账目出处，不报无照。"""
    import json
    r = _tree(tmp_path)
    new_cls = _mk(r, "域/新域/类/新类/类.md", "---\ni3dna: 类\n---\n# 新类\n")
    _mk(r, "实例/女娲/案1/x.md", "1")
    _mk(r, "实例/女娲/案1/__账/立类/__结果.json", json.dumps(
        {"产物清单": [{"名称": os.path.relpath(new_cls, r)}]},
        ensure_ascii=False))
    assert not any("新类" in w for w, m in _warns(r))


def test_无女娲_休眠(tmp_path):
    r = _tree(tmp_path)
    os.remove(os.path.join(r, "域/治理域/类/女娲/知识/宪法时刻.md"))
    rep = lint.Report()
    lint.lint_unlicensed_surgery(r, rep)          # 女娲在而基线缺席：信息休眠
    assert any("基线缺席" in m for _, m in rep.infos)
    rep2 = lint.Report()
    open(os.path.join(r, "域/治理域/类/女娲/知识/宪法时刻.md"),
         "w", encoding="utf-8").write("# 光板无表\n")
    lint.lint_unlicensed_surgery(r, rep2)         # 基线在而表空：信息休眠
    assert any("无可解析表" in m for _, m in rep2.infos)
    import shutil
    shutil.rmtree(os.path.join(r, "域", "治理域"))
    rep3 = lint.Report()
    lint.lint_unlicensed_surgery(r, rep3)         # 整个无女娲：静默休眠
    assert not rep3.warnings and not rep3.infos


def test_领域面大赦住树根_两表合并(tmp_path):
    """8-19 裁定：女娲领域无关——女娲/知识/宪法时刻.md 只留自举骨架，
    领域面大赦住树根 知识/宪法时刻-领域面.md，lint ⑦ 两表合并；
    根表缺席时领域面照旧报无照。"""
    r = _tree(tmp_path, with_baseline=False)
    # 女娲表：只放自举骨架（女娲类.md + 立类任务.md）
    meta = [os.path.join(r, "域/治理域/类/女娲/类.md"),
            os.path.join(r, "域/治理域/类/女娲/方法/立类/任务.md")]
    rows = "\n".join(
        f"| {os.path.relpath(p, r)} | "
        f"{hashlib.sha256(open(p, 'rb').read()).hexdigest()} |" for p in meta)
    _mk(r, "域/治理域/类/女娲/知识/宪法时刻.md",
        "---\ni3dna: 知识\n---\n# 宪法时刻\n\n"
        "| 路径 | sha256 |\n|---|---|\n" + rows + "\n")
    # 无根表：领域面（甲）应报无照
    hits = _warns(r)
    assert any("甲" in w and "无照手术" in m for w, m in hits), hits
    # 落根表（领域面大赦）：甲面静默
    甲面 = [os.path.join(r, "域/x域/类/甲/类.md"),
           os.path.join(r, "域/x域/类/甲/方法/办/任务.md")]
    drows = "\n".join(
        f"| {os.path.relpath(p, r)} | "
        f"{hashlib.sha256(open(p, 'rb').read()).hexdigest()} |" for p in 甲面)
    _mk(r, "知识/宪法时刻-领域面.md",
        "---\ni3dna: 知识\n---\n# 宪法时刻·领域面\n\n"
        "| 路径 | sha256 |\n|---|---|\n" + drows + "\n")
    hits = _warns(r)
    assert not any("甲" in w for w, m in hits), hits
