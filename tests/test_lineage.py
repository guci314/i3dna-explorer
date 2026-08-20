#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_lineage — 血缘面板(94号)测试:core 解析器 + UI 渲染。"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import i3dna_core as core  # noqa: E402


@pytest.mark.unit
def test_lineage_entries_无文件(tmp_path):
    assert core.lineage_entries(str(tmp_path)) == []


@pytest.mark.unit
def test_lineage_entries_解析(tmp_path):
    open(tmp_path / "__血缘.md", "w", encoding="utf-8").write(
        "状态 :: 0123456789abcdef :: P005/修改产品 :: 2026-08-17T10:00:00\n"
        "出生 :: a1b2c3d4e5f60718 :: P005/上市 :: 2026-08-17T09:00:00\n"
        "坏行没有四段\n")
    es = core.lineage_entries(str(tmp_path))
    assert len(es) == 3
    assert es[0]["键"] == "状态" and es[0]["来源"] == "P005/修改产品"
    assert es[0]["时间"] == "2026-08-17T10:00:00"
    assert es[1]["键"] == "出生"
    assert es[2]["键"] == "?" and "坏行" in es[2]["原始"]


@pytest.mark.unit
def test_lineage_panel_html(window, sample_root):
    """UI 渲染:档案袋目录带 __血缘.md → 详情含键级血缘表。"""
    d = sample_root / "_通用程序"   # 普通目录(dir 类型;蓝任务目录是 task 类型)
    (d / "__血缘.md").write_text(
        "状态 :: 0123456789abcdef :: P005/修改产品 :: 2026-08-17T10:00:00\n",
        encoding="utf-8")
    html = window._lineage_html(str(d))
    assert "键级血缘" in html
    assert "P005/修改产品" in html and "状态" in html
    # 选中该目录 → 详情面板渲染
    it = window.items_by_path.get(str(d))
    assert it is not None
    window.tree.setCurrentIndex(it.index())
    window._render_node(it)
    assert "键级血缘" in window.detail.toHtml()
