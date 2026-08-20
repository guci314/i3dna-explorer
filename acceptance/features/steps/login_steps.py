"""登录步骤——树原生主体（ARCHITECTURE §5）。对象名驱动（97 号律二）：
对话框经 do_login 的异步模态 open()，从 activeModalWidget 取，直调 _try。"""
import glob
import importlib
import os

from behave import when, then

ex = importlib.import_module("i3dna_explorer")


@when("登录主体 {ident} 口令 {pw}")
def step_login(context, ident, pw):
    from PyQt6.QtWidgets import QApplication
    context.win.do_login()
    dlg = QApplication.activeModalWidget()
    assert dlg is not None and isinstance(dlg, ex.LoginDialog), \
        "登录对话框未打开（activeModalWidget 为空或非 LoginDialog）"
    dlg.ed_principal.setText(ident)
    dlg.ed_pass.setText(pw)
    dlg._try()                      # 与点「登录」钮同链（clicked→_try）


@when("注销主体")
def step_logout(context):
    """撤下会话主体（默认主体随启动挂上——测门先撤；对话框注销钮同链）。"""
    from PyQt6.QtWidgets import QApplication
    context.win.do_login()
    dlg = QApplication.activeModalWidget()
    assert dlg is not None and isinstance(dlg, ex.LoginDialog), \
        "登录对话框未打开"
    dlg._logout()                   # 与点「注销」钮同链（clicked→_logout）


@then("工具栏显示主体 {label}")
def step_principal_label(context, label):
    txt = context.win.lbl_principal.text()
    assert label in txt, f"工具栏主体={txt!r}，期望含 {label!r}"


@then("登录日志在场 状态 {status}")
def step_login_log(context, status):
    logs = glob.glob(os.path.join(context.tree_root, "__日志", "登录_*.log"))
    ok = [p for p in logs if status in open(p, encoding="utf-8").read()]
    assert ok, (f"无状态为「{status}」的登录日志（现有 "
                f"{[os.path.basename(p) for p in logs]}）")
