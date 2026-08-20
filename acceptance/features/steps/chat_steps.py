# -*- coding: utf-8 -*-
"""右键对话（101号）step 定义——话语即签字。

判据=账/对话日志/磁盘清单（97号：账与断言不是像素）；编译车道桩在
边界（environment 注入 I3DNA_DIALOG_CMD=fake_dialog.py，只替 LLM 一环），
api 写桥/读桥与引擎管线真跑；零会话态=纯对话不落任何文件。
"""
import json
import os
import time

from behave import given, when, then   # noqa: F401

from explorer_steps import _find_item, _pump, _win


def _app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance()


def _files(root):
    """树面清单——点前缀目录整枝剪掉（.git/.obsidian 是 journal 层，
    点火/办结的 git 提交不算树面变化；只滤点文件会漏 .git 内部对象）。"""
    out = set()
    for r, ds, fs in os.walk(root):
        ds[:] = [d for d in ds if not d.startswith(".")]
        for f in fs:
            if not f.startswith("."):
                out.add(os.path.relpath(os.path.join(r, f), root))
    return out


@given("树文件快照")
@when("树文件快照")
def step_snapshot(context):
    context._snap = _files(context.tree_root)


@given("磁盘移除 {rel}")
@when("磁盘移除 {rel}")
def step_remove_file(context, rel):
    """场景自足：清掉真树遗留（在途单悬账门语义；真用过的产物/案卷——
    如真树已立过 sample_domain，验收副本须清场重演）。目录整删；
    删后向上收走空目录（空 域/ 名会撞校验程序①空域检查）。"""
    import shutil
    p = os.path.join(context.tree_root, rel)
    if os.path.isfile(p):
        os.remove(p)
    elif os.path.isdir(p):
        shutil.rmtree(p)
    d = os.path.dirname(p)
    while d.startswith(context.tree_root) and d != context.tree_root \
            and os.path.isdir(d) and not os.listdir(d):
        os.rmdir(d)
        d = os.path.dirname(d)


@given("新案卷 {shelf}/{case}")
@when("新案卷 {shelf}/{case}")
def step_new_case(context, shelf, case):
    """银行场景前置：给过程类开一个空案卷（草稿落点），刷新让树上见。"""
    os.makedirs(os.path.join(context.tree_root, "实例", shelf, case),
                exist_ok=True)
    if getattr(context, "win", None) is not None:
        context.win.refresh()
        _pump(_app())


@when("选用对话引擎 {idx:d}")
def step_pick_engine(context, idx):
    """对话起草点火的引擎车道＝工具栏选择（UI 侧注入——引擎注入在 LLM
    侧等于任意命令执行）。索引 1=OMP CLI 款（PATH 桩 omp 可截）。"""
    _win(context).cb_engine.setCurrentIndex(idx)


@then("树新增只在 {rel}")
def step_grow_only_under(context, rel):
    """两步之间树面只有案卷材料增量（103号 §8）——对照快照，新增文件
    全部落在 rel 之下（含 __账 子目录）；别处长出即违规。"""
    assert getattr(context, "_snap", None), "场景须先「树文件快照」"
    grew = {p for p in _files(context.tree_root) - context._snap}
    bad = sorted(p for p in grew if not p.startswith(rel + os.sep))
    assert not bad, f"树面在案卷外长出了东西：{bad[:5]}"


@then("批准面树新增只在 {a} 与 {b}")
def step_grow_only_under2(context, a, b):
    """批准半步的树面界：新增 ⊆ a（案卷材料/账）∪ b（落位产物）——
    落位面写出第二处文件即违规（对抗验收变异实证：无此界时引擎多写
    漏网文件全测试照样绿）。"""
    assert getattr(context, "_snap", None), "场景须先「树文件快照」"
    grew = {p for p in _files(context.tree_root) - context._snap}
    bad = sorted(p for p in grew
                 if not (p.startswith(a + os.sep) or p == b
                         or p.startswith(b + os.sep)))
    assert not bad, f"树面在案卷与落位产物之外长出了东西：{bad[:5]}"


@then("树文件清单不变")
def step_files_unchanged(context):
    assert getattr(context, "_snap", None), "场景须先「树文件快照」"
    now = _files(context.tree_root)
    assert now == context._snap, \
        (f"树面变了：+{sorted(now - context._snap)[:5]}"
         f" -{sorted(context._snap - now)[:5]}")


@when("右键 {rel} 开对话")
def step_open_chat(context, rel):
    win = _win(context)
    item = _find_item(win, rel)
    win.tree.setCurrentIndex(item.index())
    menu = win.build_dir_menu(item)
    assert menu is not None, f"{rel} 无目录菜单"
    act = next((a for a in menu.actions() if a.objectName() == "act对话"),
               None)
    assert act is not None, \
        f"菜单无「对话」: {[a.text() for a in menu.actions()]}"
    act.trigger()
    _pump(_app())


@then("菜单无对话口")
def step_menu_no_chat(context):
    win = _win(context)
    idx = win.tree.currentIndex()
    assert idx.isValid(), "树上无选中节点"
    it = win.model.itemFromIndex(idx)
    menu = win.build_dir_menu(it)
    if menu is None:
        return          # 实体实例/场所等：连菜单都无＝更无对话口
    assert not any(a.objectName() == "act对话" for a in menu.actions()), \
        f"不应有对话口: {[a.text() for a in menu.actions()]}"


@when("对话说 {speech}")
def step_say(context, speech):
    win = _win(context)
    d = getattr(win, "_chat_dlg", None)
    assert d is not None, "未开对话面板（先「右键 … 开对话」）"
    d.ed.setText(speech)
    d.send()

    def _busy():
        th = getattr(d, "_thread", None)
        if th is not None and th.isRunning():
            return True
        if any(t.isRunning() for t in getattr(win, "_chat_threads", [])):
            return True
        return getattr(d, "_pending", None) is not None

    t0, stable = time.time(), 0
    while time.time() - t0 < 30:      # 全链静定：编译线程/签字链/查询环
        _pump(_app())
        if not _busy():
            stable += 1
            if stable >= 8:           # ~0.4s 无新动作＝链路静定
                return
        else:
            stable = 0
        time.sleep(0.05)
    raise AssertionError("对话编译链 30s 未静定")


@then("对话日志含 {text}")
def step_log_has(context, text):
    d = _win(context)._chat_dlg
    assert text in d.log.toPlainText(), \
        f"对话日志缺「{text}」：\n{d.log.toPlainText()[-600:]}"


@then("对话账 {method} {case} 意图 {intent}")
def step_account_intent(context, method, case, intent):
    win = _win(context)
    p = os.path.join(context.tree_root, "实例",
                     os.path.basename(win._chat_dlg.croot), case,
                     "__账", method, "__结果.json")
    rec = json.load(open(p, encoding="utf-8"))
    assert rec.get("意图") == intent, f"意图不符：{rec.get('意图')!r}"
    assert rec.get("执行者") == win._principal["主体值"], \
        f"执行者不符：{rec.get('执行者')!r}"


@then("起草账 {method} {case} 意图 {intent} 执行者 {executor}")
def step_draft_account(context, method, case, intent, executor):
    """蓝起草站 fire 账（103号 §8 前半）：意图=第一句话语、执行者=站
    声明 agent（本职不叫代）、引擎=点火车道。"""
    win = _win(context)
    p = os.path.join(context.tree_root, "实例",
                     os.path.basename(win._chat_dlg.croot), case,
                     "__账", method, "__结果.json")
    rec = json.load(open(p, encoding="utf-8"))
    assert rec.get("意图") == intent, f"意图不符：{rec.get('意图')!r}"
    assert rec.get("执行者") == executor, f"执行者不符：{rec.get('执行者')!r}"
    assert rec.get("引擎"), "引擎车道须入账"
