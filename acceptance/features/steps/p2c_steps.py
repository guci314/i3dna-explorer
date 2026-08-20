# -*- coding: utf-8 -*-
"""P2c step 定义——通用界面(人工工位办理)验收,对象名驱动+边界打桩。

通用界面=聊天收参+编辑器+唯一确认按钮,领域无关。判据=断言与账
(工单绑定/磁盘/桩引擎参数),证据=widget.grab 落盘 PNG。
LLM 车道桩掉(assist_proc_run 换桩),机械链(开单/销单/入账)真跑;
引擎走 _engine_qproc 捕获断言 args——桩只替外部调用一环。
命名注意:context 属性勿用 captured(behave 内部占用,会在层压栈时
被覆写为 NoCaptured,桩内 .update 抛错直接 PyQt fatal abort)。
"""
import os

from behave import given, when, then   # noqa: F401


@given("磁盘铺澄清单 {case}")
@when("磁盘铺澄清单 {case}")
def step_seed_ticket(context, case):
    """场景自足:真树的澄清单可能已被历史办结销掉,铺一张在场单。"""
    fp = os.path.join(context.tree_root, "实例/研发", case, "需求/澄清单.md")
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        f.write("---\nclarify_round: 1\n状态: 待澄清\n---\n\n"
                "问: 目标函数语义?\n")
    _win(context).refresh()
    _pump(_app())


from explorer_steps import _find_item, _pump, _win


def _app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance()


@when("办理工位 {task} 实例 {case}")
def step_open_work(context, task, case):
    win = _win(context)
    win._assist_proc_run = lambda prompt: None      # 桩 LLM 车道
    for t in win.tasks:
        if os.path.basename(t) == task:
            win.open_work_ui(t, case)
            _pump(_app())
            return
    raise AssertionError(f"无任务 {task}")


@when("双击文件 {rel}")
def step_double_click(context, rel):
    win = _win(context)
    win._assist_proc_run = lambda prompt: None
    item = _find_item(win, rel)
    win.tree.setCurrentIndex(item.index())
    win._render_node(item)          # 与 on_select 真实分发同一条路
    _pump(_app())


@when("引擎走桩并点击确认按钮")
def step_confirm(context):
    win = _win(context)
    holder = {}

    def _stub(*a, **k):
        holder["args"] = a          # 桩内禁抛( Qt slot 异常=fatal abort )
    win._engine_qproc = _stub
    # 重办结防覆盖（8-19）：m1 副本上案卷已有账且场景铺垫了新输入→
    # 确认时弹问询模态。exec 模态内 singleShot 可达——自动答「是」，
    # 防覆盖语义本身由单测钉（test_new_case）。
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QMessageBox

    def _auto_yes():
        m = _app().activeModalWidget()
        if isinstance(m, QMessageBox):
            y = m.button(QMessageBox.StandardButton.Yes)
            if y is not None:
                y.click()
    QTimer.singleShot(0, _auto_yes)
    QTimer.singleShot(300, _auto_yes)
    btn = win.findChild(type(win.btn_confirm), "btnConfirm")
    assert btn is not None, "找不到对象名 btnConfirm"
    btn.click()
    _pump(_app())
    context.workui_args = holder.get("args")


@then("编辑器已载入 {rel}")
def step_editor_loaded(context, rel):
    win = _win(context)
    fp = os.path.join(win.root, rel)
    assert getattr(win, "_edit_path", None) == fp, \
        f"编辑器载入 {win._edit_path} ≠ {fp}"


@then("确认按钮可见")
def step_confirm_visible(context):
    assert not _win(context).btn_confirm.isHidden(), "确认按钮未现身"


@then("确认按钮已隐藏")
def step_confirm_hidden(context):
    assert _win(context).btn_confirm.isHidden(), "确认按钮未隐藏"


@then("工单已绑定 {task} {case}")
def step_work_bound(context, task, case):
    w = _win(context)._work
    assert w is not None, "工单未绑定"
    assert os.path.basename(w["tdir"]) == task, f"工位 {w['tdir']} ≠ {task}"
    assert w["case"] == case, f"实例 {w['case']} ≠ {case}"


@then("工单已解绑")
def step_work_unbound(context):
    assert _win(context)._work is None, "工单仍绑定"


@then("工位依据含 {doc}")
def step_inputs_have(context, doc):
    w = _win(context)._work
    assert w is not None, "工单未绑定"
    assert doc in w["inputs"], f"依据缺 {doc}: {list(w['inputs'])}"


@then("磁盘不存在 {rel}")
def step_disk_missing(context, rel):
    fp = os.path.join(context.tree_root, rel)
    assert not os.path.exists(fp), f"{rel} 仍存在（单据未销）"


@then("桩引擎收到办结参数")
def step_engine_args(context):
    a = getattr(context, "workui_args", None)
    flat = [x for item in (a or ()) for x in
            (item if isinstance(item, list) else [item])]
    assert "backfill" in flat and "--case" in flat, f"args 异常: {a}"
