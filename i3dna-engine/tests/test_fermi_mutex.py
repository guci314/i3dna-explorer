# -*- coding: utf-8 -*-
"""lint ⑥ 认领互斥（费米律：一域至多被一份声明认领——8-19 审计补的
通用检查器侧执法面；此前只有树内校验程序执法）。
两臂：双声明认领同域报错／「全部」与具体认领冲突报错。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LINT = os.path.join(os.path.dirname(os.path.dirname(HERE)), "i3dna-lint",
                    "i3dna_lint.py")
sys.path.insert(0, os.path.dirname(LINT))

import i3dna_lint as lint   # noqa: E402


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _tree(tmp_path, decls):
    r = str(tmp_path)
    for d in ("甲域", "乙域"):
        _mk(r, f"域/{d}/域.md", "域主: x\n")
    for 名, 装配 in decls.items():
        _mk(r, f"场所/{名}.md",
            f"---\n场所主: x\n职责: y\n装配: [{装配}]\n---\n")
    return r


def _errs(root):
    rep = lint.Report()
    lint.lint_logical_model(root, rep)
    return [msg for *_, msg in rep.errors]


def test_双声明认领同域报错(tmp_path):
    r = _tree(tmp_path, {"台A": "甲域", "台B": "甲域"})
    errs = _errs(r)
    assert any("费米律破坏" in m and "甲域" in m for m in errs), errs


def test_全部与具体认领冲突(tmp_path):
    r = _tree(tmp_path, {"全景": "全部", "台B": "乙域"})
    errs = _errs(r)
    assert any("费米律破坏" in m and "乙域" in m for m in errs), errs


def test_互不冲突零报错(tmp_path):
    r = _tree(tmp_path, {"台A": "甲域", "台B": "乙域"})
    assert not _errs(r)
