# -*- coding: utf-8 -*-
"""test_api — Agent API（i3dna_api）测试：读桥 JSON 面 + 写桥直通引擎。

驱动=真实 CLI 子进程（agent 同款姿势，非 import 直调）；判据=JSON+
账+文件（97 号：判据是账不是像素）。桩引擎只替 LLM 一环，暂存-验收-
落位-账全链路真跑（P2b 同款边界打桩）。"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.join(os.path.dirname(HERE), "i3dna_api.py")

TASK = """---
i3dna: 微任务
输入:
  - "{实例}/申请.md"
产物:
  - "{实例}/出.md"
---
干活。
"""

GATED = TASK.replace("---\n", "---\n校验: 门.py\n", 1)

STUB = """import os, re, sys
prompt = sys.stdin.read()
for p in re.findall(r"【产物→写到】(\\S+)", prompt):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("桩产物\\n")
print("完成")
"""


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _tree(tmp_path, task=TASK):
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/方法/办/任务.md", task)
    _mk(r, "实例/甲/c1/申请.md", "---\n键: 值\n---\n申请。\n")
    _mk(r, "桩.py", STUB)
    return r


def call(verb, root, *flags):
    return subprocess.run([sys.executable, API, verb, root, *flags],
                          capture_output=True, text=True)


def _j(r):
    return json.loads(r.stdout)


def test_读桥_tree_tasks_task(tmp_path):
    r = str(tmp_path)
    _tree(tmp_path)
    d = _j(call("tree", r))
    assert [x["名"] for x in d["域"]] == ["x域"]
    甲 = next(c for c in d["类"] if c["名"] == "甲")
    assert 甲["范畴"] == "过程" and 甲["方法"][0]["名"] == "办"
    assert d["场所"] and d["场所"][0]["是根场所"]      # 根场所=全类

    d = _j(call("tasks", r))
    t = d["任务"][0]
    assert t["路径"] == "域/x域/类/甲/方法/办" and t["案卷们"] == ["c1"]

    d = _j(call("task", r, "--task", "域/x域/类/甲/方法/办", "--case", "c1"))
    arcs = {(x["弧"], x["名"]): x for x in d["弧"]}
    assert arcs[("输入", "申请.md")]["在场"]
    assert arcs[("产物", "出.md")]["路径"] == "实例/甲/c1/出.md"


def test_读桥_拒绝也机读(tmp_path):
    r = _tree(tmp_path)
    x = call("task", r, "--task", "域/x域/类/甲/方法/无此法", "--case", "c1")
    assert x.returncode == 2 and _j(x)["拒绝"]


def test_写桥_fire_settle_闭环(tmp_path):
    r = _tree(tmp_path)
    f = call("fire", r, "--task", "域/x域/类/甲/方法/办", "--case", "c1",
             "--engine", f"{sys.executable} {os.path.join(r, '桩.py')}",
             "--executor", "实例/人员/测试员")
    assert f.returncode == 0, f.stderr
    assert os.path.isfile(os.path.join(r, "实例", "甲", "c1", "出.md"))
    d = _j(call("account", r, "--task", "域/x域/类/甲/方法/办", "--case", "c1"))
    rec = d["账"][0]["记录"]
    assert rec["状态"] == "执行" and rec["执行者"] == "实例/人员/测试员"
    assert rec["产物清单"][0]["sha256"]                      # 判据=账记 sha

    s = call("settle", r, "--task", "域/x域/类/甲/方法/办", "--case", "c1",
             "--note", "api 办结")
    assert s.returncode == 0, s.stderr
    d = _j(call("account", r, "--task", "域/x域/类/甲/方法/办", "--case", "c1"))
    assert d["账"][0]["记录"]["状态"] == "事后追认"


def test_写桥_校验门拒绝零副作用(tmp_path):
    r = _tree(tmp_path, GATED)
    _mk(r, "门.py", "import sys\nsys.stderr.write('不合法\\n')\nsys.exit(1)\n")
    s = call("settle", r, "--task", "域/x域/类/甲/方法/办", "--case", "c1")
    assert s.returncode != 0
    d = _j(call("account", r, "--task", "域/x域/类/甲/方法/办", "--case", "c1"))
    assert not d["账"], "校验门拒绝时不得写账"


def test_写桥_login入账(tmp_path):
    r = _tree(tmp_path)
    x = call("login", r, "--principal", "实例/人员/刘亦菲",
             "--status", "登录成功")
    assert x.returncode == 0, x.stderr
    logs = [f for f in os.listdir(os.path.join(r, "__日志"))
            if f.startswith("登录_") and "刘亦菲" in f]
    assert logs, "登录日志未落账"


def test_写桥_办结入git_journal(tmp_path):
    """办结也是事件（8-19 补，对齐点火）：有 git 的树 settle 留 journal
    提交——绿任务手术（女娲）的留痕审计才完整。"""
    import subprocess as sp
    r = _tree(tmp_path)
    sp.run(["git", "init", "-q", r], check=True)
    sp.run(["git", "-C", r, "config", "user.email", "t@t"], check=True)
    sp.run(["git", "-C", r, "config", "user.name", "t"], check=True)
    f = call("fire", r, "--task", "域/x域/类/甲/方法/办", "--case", "c1",
             "--engine", f"{sys.executable} {os.path.join(r, '桩.py')}")
    assert f.returncode == 0, f.stderr
    s = call("settle", r, "--task", "域/x域/类/甲/方法/办", "--case", "c1",
             "--note", "api 办结")
    assert s.returncode == 0, s.stderr
    log = sp.run(["git", "-C", r, "log", "--oneline"],
                 capture_output=True, text=True).stdout
    assert "办结" in log, log
    assert "点火" in log, log


def test_lint_退出码随错误(tmp_path):
    r = _tree(tmp_path)
    d = _j(call("lint", r))
    assert "错误" in d and "警告" in d
    assert call("lint", r).returncode == (1 if d["错误"] else 0)


# ── 对抗评审坐实缺陷的回归钉（8-19 三镜头 22 agent 实测复现后修复） ──

def test_缺task旗标_机读拒绝不是崩栈(tmp_path):
    """task 动词漏 --task：{拒绝}+码 2，不是 AttributeError 栈（契约）。"""
    r = _tree(tmp_path)
    x = call("task", r)
    assert x.returncode == 2 and _j(x)["拒绝"]


def test_树根不存在_统一机读拒绝(tmp_path):
    x = call("tree", os.path.join(str(tmp_path), "没有这棵树"))
    assert x.returncode == 2 and _j(x)["拒绝"]
    assert call("lint", os.path.join(str(tmp_path), "没有这棵树")).returncode == 2


def test_task路径越界_响亮拒绝(tmp_path):
    """../ 段越出树根=拒绝；读预检与写桥同守（fire 不把账写根外）。"""
    r = _tree(tmp_path)
    _mk(str(tmp_path), "外面/方法/跨法/任务.md", TASK)
    for verb_args in (("task", r, "--task", "../外面/方法/跨法"),
                      ("fire", r, "--task", "../外面/方法/跨法")):
        x = call(*verb_args)
        assert x.returncode == 2 and _j(x)["拒绝"], verb_args


TASK_CLASS = """---
i3dna: 微任务
产物:
  - "出.md"
---
干活。
"""


def test_advance_直通树根可用(tmp_path):
    """advance 不带 --task（文档用法）＝ converge 吃树根，不崩不错域。"""
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/方法/办/任务.md", TASK_CLASS)   # 类级任务
    x = call("advance", r, "--plan")
    assert x.returncode == 0, x.stderr + x.stdout


def test_advance_外类内容记号不炸全根推进(tmp_path):
    """帧容错（8-19 猎证回归钉）：全根推进遇外类内容记号任务（{申请.域}
    在本案卷帧缺载荷）按未实例化聚合跳过，不 SystemExit 炸整个 converge
    ——女娲落地次日工具栏扇出推进曾全线失败，即此形。"""
    r = _tree(tmp_path)
    _mk(r, "域/x域/类/女娲式/类.md", "---\ni3dna: 类\n---\n# 女娲式\n")
    _mk(r, "域/x域/类/女娲式/方法/立类/任务.md",
        "---\ni3dna: 微任务\n输入:\n  - \"{实例}/申请.md\"\n"
        "产物:\n  - \"域/{申请.域}/类/X/类.md\"\n---\nx\n")
    x = call("advance", r, "--plan", "--case", "c1")
    assert x.returncode == 0, x.stderr + x.stdout
    assert "内容记号" not in x.stdout, "缺载荷任务应聚合跳过而非裸抛"
    assert "与之无关" in x.stdout
    x = call("advance", r, "--plan")                    # 无 case 帧（全 marked）
    assert x.returncode == 0, x.stderr + x.stdout


def test_坏账露出不吞不崩(tmp_path):
    """一条坏账 JSON：不崩栈、以「坏账」行露出——审计面不许账目凭空消失。"""
    r = _tree(tmp_path)
    f = call("fire", r, "--task", "域/x域/类/甲/方法/办", "--case", "c1",
             "--engine", f"{sys.executable} {os.path.join(r, '桩.py')}")
    assert f.returncode == 0, f.stderr
    acc = os.path.join(r, "实例", "甲", "c1", "__账", "办", "__结果.json")
    with open(acc, "w", encoding="utf-8") as fh:
        fh.write("{corrupted!!")
    d = _j(call("account", r))
    assert d.get("坏账") and not d["账"], d
    assert "账目录" in d["坏账"][0]


def test_账目定义侧坏_不静默消失(tmp_path):
    """任务已点火后 任务.md 被破坏：账目仍在清单（账本盘直读）。"""
    r = _tree(tmp_path)
    f = call("fire", r, "--task", "域/x域/类/甲/方法/办", "--case", "c1",
             "--engine", f"{sys.executable} {os.path.join(r, '桩.py')}")
    assert f.returncode == 0, f.stderr
    with open(os.path.join(r, "域/x域/类/甲/方法/办/任务.md"),
              "w", encoding="utf-8") as fh:
        fh.write("frontmatter 没了\n")           # 定义侧坏（人为破坏）
    d = _j(call("account", r, "--case", "c1"))
    assert d["账"], "已点火的账目不得因定义侧损坏而凭空消失"
    assert d["账"][0]["账目录"].endswith(
        os.path.join("实例", "甲", "c1", "__账", "办"))


def test_coverage_退出码随缺口(tmp_path):
    r = _tree(tmp_path)                          # 未点火=有缺口
    x = call("coverage", r)
    assert x.returncode == 1 and _j(x)["变迁覆盖"]["未点火"]


def test_yaml标量不崩json(tmp_path):
    """frontmatter 写日期形标量（yaml→date）：default=str 兜住。"""
    r = _tree(tmp_path, TASK.replace("干活。\n", "干活。\n执行者: 2026-01-01\n"))
    d = _j(call("tasks", r))                     # 原样文本，不改 frontmatter 结构
    assert d["任务"]


def test_任务定义族_正文双横线不崩(tmp_path):
    """__*任务定义*.md 正文含 --- 分隔线：非映射 YAML 不算 frontmatter。"""
    r = _tree(tmp_path)
    _mk(r, "域/x域/类/甲/方法/旧法/__旧任务定义.md",
        "自由指令正文\n---\n注意\n- 一条\n---\n收尾\n")
    d = _j(call("tasks", r))
    assert any("旧法" in t["路径"] for t in d["任务"])


def test_案卷号记号_同引擎判定(tmp_path):
    """纯 {案卷号} 跨架弧任务与 {实例} 同算 marked，案卷们照列。"""
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/立项/类.md", "---\ni3dna: 类\n---\n# 立项\n")
    _mk(r, "域/x域/类/立项/方法/受理/任务.md",
        "---\ni3dna: 微任务\n产物:\n  - \"实例/立项/{案卷号}/受理.md\"\n---\nx\n")
    _mk(r, "实例/立项/A1/x.md", "1")
    d = _j(call("tasks", r))
    t = next(t for t in d["任务"] if t["路径"].endswith("受理"))
    assert t["案卷们"] == ["A1"]


def test_过滤动词越界_理由对齐(tmp_path):
    """tasks/account 的 --task 越界＝越出树根拒绝（不是「任务不存在」）。"""
    r = _tree(tmp_path)
    for v in ("tasks", "account"):
        x = call(v, r, "--task", "../../etc")
        assert x.returncode == 2 and "越出树根" in _j(x)["拒绝"], v
    x = call("tasks", r, "--task", "./域/x域/类/甲/方法/办")   # 非规范拼法可用
    assert x.returncode == 0 and _j(x)["任务"]


def test_账写暂存名带pid_并发不撞(tmp_path):
    """账 save 的 tmp 带 pid 后缀——并发双写不共享暂存名（8-19 猎证：
    固定名下对方抢先 rename 会让本方 FileNotFoundError 崩栈）。"""
    sys.path.insert(0, os.path.dirname(HERE))
    import i3dna_store
    seen = []
    real_replace = os.replace

    def spy(src, dst):
        seen.append(os.path.basename(src))
        return real_replace(src, dst)

    orig = i3dna_store.os.replace
    i3dna_store.os.replace = spy
    try:
        out = i3dna_store.JsonAccountStore().save(str(tmp_path), {"x": 1})
    finally:
        i3dna_store.os.replace = orig
    assert seen == [f"__结果.json.tmp.{os.getpid()}"], seen
    assert os.path.basename(out) == "__结果.json"
