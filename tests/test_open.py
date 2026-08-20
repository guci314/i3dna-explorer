#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_open — 文件菜单:打开目录 / 打开最近的目录。"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import i3dna_core as core  # noqa: E402


# ── core 无头 ────────────────────────────────────────

@pytest.mark.unit
def test_recent_save_load(tmp_path):
    f = str(tmp_path / "recent.json")
    assert core.recent_roots_load(f) == []
    a = str(tmp_path / "甲")
    b = str(tmp_path / "乙")
    os.makedirs(a)
    os.makedirs(b)
    core.recent_roots_save(a, f)
    core.recent_roots_save(b, f)
    core.recent_roots_save(a, f)          # 重复 → 去重并置顶
    roots = core.recent_roots_load(f)
    assert roots == [a, b]


@pytest.mark.unit
def test_recent_cap(tmp_path):
    f = str(tmp_path / "recent.json")
    for i in range(15):
        d = str(tmp_path / f"d{i}")
        os.makedirs(d)
        core.recent_roots_save(d, f)
    assert len(core.recent_roots_load(f)) == core.RECENT_MAX


# ── UI ────────────────────────────────────────

@pytest.mark.unit
def test_file_menu_exists(window):
    labels = [a.text() for a in window.menuBar().actions()]
    assert "文件" in labels
    文件 = next(a.menu() for a in window.menuBar().actions() if a.text() == "文件")
    sub = {a.text() for a in 文件.actions() if a.text()}
    assert {"打开目录…", "打开最近的目录", "退出"} <= sub


@pytest.mark.unit
def test_open_root_switches_tree(window, sample_root, tmp_path):
    new = tmp_path / "另一棵树"
    new.mkdir()
    (new / "任务.md").write_text(
        "---\n执行者: LLM\n---\n# 另一棵\n", encoding="utf-8")
    window.open_root(str(new))
    assert "另一棵树" in window.windowTitle()
    root_item = window.model.item(0)
    assert root_item.text().startswith("另一棵树")   # 根级任务.md 会带状态后缀
    # 最近清单已更新(隔离在 tmp 的 recent.json)
    assert str(new) in core.recent_roots_load()


@pytest.mark.unit
def test_recent_menu_fill(window, tmp_path):
    d = tmp_path / "甲树"
    d.mkdir()
    window.open_root(str(d))
    window._fill_recent_menu()
    labels = [a.text() for a in window.recent_menu.actions() if a.text()]
    assert any(str(d) in l for l in labels)
