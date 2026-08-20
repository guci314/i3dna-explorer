#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_coverage — MBT 覆盖报告(P3):变迁/边覆盖语义。"""
import os

import pytest

import i3dna_core as core

TREE = os.path.join(core.BASE, "trade-v4")   # 树在引擎仓（explorer 已迁出独立安家）


@pytest.mark.unit
def test_coverage_shape_and_facts():
    rep = core.coverage_report(TREE)
    nf, nt = rep["变迁覆盖"]
    kw, ke = rep["边覆盖"]
    assert nt == 10, "trade-v4 应有 10 个微任务"
    assert nf + len(rep["未点火"]) == nt
    assert ke == len(rep["边"])
    assert kw == len(rep["已走过"])
    names = {os.path.basename(t) for t in rep["已点火"]}
    assert "上市" in names, "上市有账应计点火"
    assert "出库" not in names, "出库无账应计未点火"
    fired = set(rep["已点火"])
    assert all(u in fired and v in fired for u, v, _p in rep["已走过"]), \
        "走过边两端必有账"


@pytest.mark.integration
def test_coverage_cli():
    import subprocess
    import sys
    eng_py = os.path.join(core.BASE, "i3dna-engine", "i3dna_engine.py")
    r = subprocess.run([sys.executable, eng_py, "coverage", TREE],
                       capture_output=True, text=True)
    assert r.returncode == 1, "trade-v4 有缺口应退出码 1"
    assert "变迁覆盖" in r.stdout and "边覆盖" in r.stdout
    assert "未点火" in r.stdout and "未走过" in r.stdout
