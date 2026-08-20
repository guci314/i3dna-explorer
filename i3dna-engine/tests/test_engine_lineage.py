# -*- coding: utf-8 -*-
"""血缘(94号)测试:引擎附注 + lint 判据。纯 tmp 树,零点火。"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ENG = os.path.join(os.path.dirname(HERE), "i3dna_engine.py")
LINT = os.path.join(os.path.dirname(os.path.dirname(HERE)), "i3dna-lint", "i3dna_lint.py")
sys.path.insert(0, os.path.dirname(ENG))
sys.path.insert(0, os.path.dirname(LINT))

import i3dna_engine as eng  # noqa: E402
import i3dna_lint as lint  # noqa: E402


def _mk_field(tmp_path, content="状态: 在售\n"):
    f = os.path.join(str(tmp_path), "字段区", "状态.md")
    os.makedirs(os.path.dirname(f), exist_ok=True)
    open(f, "w", encoding="utf-8").write(content)
    return f


def test_血缘_改键附注(tmp_path):
    f = _mk_field(tmp_path)
    task = {"task_dir": os.path.join(str(tmp_path), "方法", "修改产品"),
            "root": str(tmp_path), "case": "P005"}
    snaps = {"状态": ({"path": f}, {"状态": "在售"}, "---\n状态: 在售\n---\n".encode())}
    open(f, "w", encoding="utf-8").write("---\n状态: 下架\n---\n")
    eng._append_lineage_for(task, snaps, "2026-08-17T10:00:00")
    lf = os.path.join(os.path.dirname(f), "__血缘.md")
    lines = open(lf, encoding="utf-8").read().splitlines()
    assert len(lines) == 1
    k, h, src, ts = [p.strip() for p in lines[0].split("::")]
    assert k == "状态" and src == "P005/修改产品" and ts == "2026-08-17T10:00:00"
    assert len(h) == 16
    # 再改一次 → 追加第二条(不覆盖)
    snaps2 = {"状态": ({"path": f}, {"状态": "下架"}, "---\n状态: 下架\n---\n".encode())}
    open(f, "w", encoding="utf-8").write("---\n状态: 在售\n---\n")
    eng._append_lineage_for(task, snaps2, "2026-08-17T11:00:00")
    lines = open(lf, encoding="utf-8").read().splitlines()
    assert len(lines) == 2 and "11:00:00" in lines[1]


def test_血缘_出生(tmp_path):
    f = _mk_field(tmp_path, "")
    open(f, "w", encoding="utf-8").write("---\n状态: 在售\n---\n")
    task = {"task_dir": os.path.join(str(tmp_path), "方法", "上市"),
            "root": str(tmp_path), "case": "P005"}
    snaps = {"状态": ({"path": f}, {}, None)}   # raw None = 出生
    eng._append_lineage_for(task, snaps, "2026-08-17T09:00:00")
    lines = open(os.path.join(os.path.dirname(f), "__血缘.md"),
                 encoding="utf-8").read().splitlines()
    assert lines[0].startswith("出生 :: ")


def test_血缘_执法断线已接回(tmp_path, monkeypatch):
    """_field_guard 曾被定义未调用(执法断线);接回后:越权改键 → SystemExit。"""
    f = _mk_field(tmp_path)
    状态md = os.path.join(str(tmp_path), "状态", "状态.md")
    os.makedirs(os.path.dirname(状态md), exist_ok=True)
    open(状态md, "w", encoding="utf-8").write(
        "---\n属主:\n  状态: 产品管理\n---\n")
    monkeypatch.setattr(eng, "_type_file", lambda *a, **k: 状态md)
    task = {"task_dir": os.path.join(str(tmp_path), "方法", "上市"),
            "root": str(tmp_path)}
    snaps = {"状态": ({"path": f, "pname": "状态"}, {"状态": "在售"},
                      "---\n状态: 在售\n---\n".encode())}
    open(f, "w", encoding="utf-8").write("---\n状态: 下架\n---\n")
    with pytest.raises(SystemExit):
        eng._field_guard(task, snaps)
    # 越权被回滚:文件回到点火前字节
    assert open(f, encoding="utf-8").read() == "---\n状态: 在售\n---\n"


def test_lint_血缘(tmp_path):
    lf_dir = os.path.join(str(tmp_path), "实例", "产品", "P005")
    os.makedirs(lf_dir, exist_ok=True)
    lf = os.path.join(lf_dir, "__血缘.md")
    open(lf, "w", encoding="utf-8").write(
        "状态 :: 0123456789abcdef :: P005/修改产品 :: 2026-08-17T10:00:00\n"
        "状态 :: fedcba9876543210 :: P005/修改产品 :: 2026-08-17T09:00:00\n"
        "坏行没有四段\n")
    rep = lint.lint_tree(str(tmp_path))
    msgs = [m for _, m in rep.errors]
    assert any("格式错" in m for m in msgs), msgs
    assert any("时间回退" in m for m in msgs), msgs
