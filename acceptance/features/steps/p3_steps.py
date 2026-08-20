# -*- coding: utf-8 -*-
"""P3/P4 step 定义——覆盖报告(MBT)与视觉基线(golden)。

判据=断言(覆盖计数/像素差异),证据=widget.grab() 落盘 PNG。
基线在 baselines/,记录用「记录视觉基线」步,变更需人工审基线(不盲更新)。
"""
import os

from behave import then, when   # noqa: F401
from PyQt6.QtGui import QImage

from environment import BASELINES
from explorer_steps import _pump, _win


def _app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance()


@when("记录视觉基线 {name}")
def step_record_baseline(context, name):
    win = _win(context)
    win.resize(1280, 800)
    win.show()
    _pump(_app(), 200)
    os.makedirs(BASELINES, exist_ok=True)
    win.tree.grab().save(os.path.join(BASELINES, f"tree_{name}.png"))


@then("树视图与基线一致 {name}")
def step_baseline(context, name):
    win = _win(context)
    base = os.path.join(BASELINES, f"tree_{name}.png")
    assert os.path.isfile(base), f"无基线 {base}"
    ref = QImage(base)
    cur = win.tree.grab().toImage()
    assert ref.size() == cur.size(), f"基线尺寸 {ref.size()} ≠ 当前 {cur.size()}"
    diff = 0
    for y in range(0, ref.height(), 2):      # 隔行隔列采样,抗锯齿容忍
        for x in range(0, ref.width(), 2):
            if ref.pixel(x, y) != cur.pixel(x, y):
                diff += 1
    total = max(1, (ref.height() // 2) * (ref.width() // 2))
    ratio = diff / total
    assert ratio < 0.005, f"与基线差异 {diff}/{total} = {ratio:.4f}"
