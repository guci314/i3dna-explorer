# -*- coding: utf-8 -*-
"""api 验收步骤——agent 经 i3dna_api.py 与目录体系交互。

判据=JSON+账+文件（97 号）；打桩只替 LLM 一环（fakes/fake_engine.py，
write 车道解析【产物→写到】逐产物写桩内容），引擎侧全链路真跑。
证据链=API 的 JSON 输出落 evidence（无 UI，无截图）。"""
import json
import os
import subprocess
import sys

from behave import given, when, then

HERE = os.path.dirname(os.path.abspath(__file__))          # features/steps
ACCEPT = os.path.dirname(os.path.dirname(HERE))            # acceptance/
EXPLORER_DIR = os.path.dirname(ACCEPT)                     # i3dna-explorer/
REPO = os.path.dirname(EXPLORER_DIR)                       # report_generate/
API = os.path.join(REPO, "i3dna-engine", "i3dna_api.py")
FAKE_ENGINE = os.path.join(ACCEPT, "fakes", "fake_engine.py")
EVIDENCE = os.path.join(ACCEPT, "evidence")

TASK = """---
i3dna: 微任务
输入:
  - "{实例}/申请.md"
产物:
  - "{实例}/出.md"
---
干活。
"""


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _api(context, verb, *flags):
    r = subprocess.run([sys.executable, API, verb, context.api_root, *flags],
                       capture_output=True, text=True)
    context.proc = r
    return r


def _j(context):
    return json.loads(context.proc.stdout)


@given("一棵最小验收树")
def _mintree(context):
    r = os.path.join(context.tmp, "apitree")
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/方法/办/任务.md", TASK)
    _mk(r, "实例/甲/c1/申请.md", "---\n键: 值\n---\n申请。\n")
    context.api_root = r


@given("一棵带拒绝门的验收树")
def _mintree_gated(context):
    _mintree(context)
    _mk(context.api_root, "域/x域/类/甲/方法/办/任务.md",
        TASK.replace("---\n", "---\n校验: 门.py\n", 1))
    _mk(context.api_root, "门.py",
        "import sys\nsys.stderr.write('不合法（api 验收）\\n')\nsys.exit(1)\n")


CARD = ("# API手艺（老师傅的读桥）\n\n只许读：tree/tasks/task/account/"
        "lint/coverage；判据是账不是印象。\n")


@given("一棵带手艺卡的最小验收树")
def _mintree_skilled(context):
    """最小树+手艺卡：老子升老师傅（presence-based 技能，零第二登记）。
    树写进 context.tree_root——_win 在此树上开窗。"""
    _mintree(context)
    _mk(context.api_root, "域/治理域/类/目录树元知识/知识/API手艺.md", CARD)
    import shutil
    shutil.rmtree(context.tree_root)
    shutil.copytree(context.api_root, context.tree_root)
    context.win = None                      # 强制 _win 在新树上重开窗


@then("老子查过真 API")
def step_laozi_queried(context):
    """判据=【查】转写里躺着真 API 的 JSON（桩只替 LLM，读桥真跑）。"""
    win = getattr(context, "win", None)
    if win is None:
        import i3dna_explorer as ex
        win = context.win = ex.Explorer(context.tree_root)
    queries = [t for who, t in win._chat_log if who == "查"]
    assert queries, "无【查】转写——老师傅没盘问"
    assert "【查】tasks" in queries[0] and '"任务"' in queries[0], queries[0][:200]


@when("agent 调 API tree")
def _tree(context):
    _api(context, "tree")


@then("JSON 含 域 x域 类 甲 方法 办 与 根场所")
def _tree_ok(context):
    d = _j(context)
    assert [x["名"] for x in d["域"]] == ["x域"]
    甲 = next(c for c in d["类"] if c["名"] == "甲")
    assert 甲["范畴"] == "过程" and 甲["方法"][0]["名"] == "办"
    assert d["场所"][0]["是根场所"] and "甲" in d["场所"][0]["类集"]


@when("agent 调 API 预检任务 办 案卷 c1")
def _task(context):
    _api(context, "task", "--task", "域/x域/类/甲/方法/办", "--case", "c1")


@then("JSON 弧 申请.md 在场 产物弧指向 实例/甲/c1/出.md")
def _task_ok(context):
    arcs = {(x["弧"], x["名"]): x for x in _j(context)["弧"]}
    assert arcs[("输入", "申请.md")]["在场"]
    assert arcs[("产物", "出.md")]["路径"] == "实例/甲/c1/出.md"


@when("agent 调 API 桩引擎点火 办 案卷 c1")
def _fire(context):
    _api(context, "fire", "--task", "域/x域/类/甲/方法/办", "--case", "c1",
         "--engine", f"{sys.executable} {FAKE_ENGINE}")


@then("产物文件 实例/甲/c1/出.md 在场")
def _prod(context):
    assert context.proc.returncode == 0, context.proc.stderr
    assert os.path.isfile(os.path.join(context.api_root,
                                       "实例", "甲", "c1", "出.md"))


def _account(context):
    _api(context, "account", "--task", "域/x域/类/甲/方法/办", "--case", "c1")
    with open(os.path.join(EVIDENCE, "api_账.json"), "w", encoding="utf-8") as f:
        f.write(context.proc.stdout)                     # 证据链=JSON 落盘
    return _j(context)["账"][0]["记录"]


@then("账记 状态 执行 产物清单带 sha256")
def _acc_fire(context):
    rec = _account(context)
    assert rec["状态"] == "执行"
    assert rec["产物清单"][0]["sha256"]


@when("agent 调 API 办结 办 案卷 c1")
def _settle(context):
    _api(context, "settle", "--task", "域/x域/类/甲/方法/办", "--case", "c1")


@then("账记 状态 事后追认")
def _acc_settle(context):
    assert context.proc.returncode == 0, context.proc.stderr
    rec = _account(context)
    assert rec["状态"] == "事后追认"


@then("退出码非零 账未写")
def _gate_reject(context):
    assert context.proc.returncode != 0, "校验门拒绝应非零退出"
    _api(context, "account", "--task", "域/x域/类/甲/方法/办", "--case", "c1")
    assert not _j(context)["账"], "拒绝时不得写账（零副作用）"
