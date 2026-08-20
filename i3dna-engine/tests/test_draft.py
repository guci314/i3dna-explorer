# -*- coding: utf-8 -*-
"""写桥 draft（101号 起草车道·103号 审批入图）：草稿落案卷零入账；
产物槽落位=审批前半步（路径须恰为本任务产物弧）；防注入与封存门同
fire/settle。判据=磁盘与退出码（97 号：断言与账）。"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "i3dna_engine.py")
API = os.path.join(os.path.dirname(HERE), "i3dna_api.py")

TASK = """---
i3dna: 微任务
执行者: 人
输入:
  - "{实例}/申请.md"
产物:
  - "域/{申请.域名}/域.md"
---
结构手术·审批站。
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
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n范畴: 过程\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/方法/办/任务.md", task)
    _mk(r, "实例/甲/c1/申请.md", "---\n域名: d9\n域主: 张三\n---\n申请。\n")
    _mk(r, "实例/甲/c1/域.md", "---\n域主: 张三\n职责: 示范\n---\n域草稿\n")
    return r


def _draft(r, task_rel, case, payload, api=False):
    if api:
        cmd = [sys.executable, API, "draft", r, "--task", task_rel]
        if case:
            cmd += ["--case", case]
    else:
        tdir = os.path.join(r, task_rel)
        cmd = [sys.executable, ENGINE, "draft", tdir, "--root", r]
        if case:
            cmd += ["--case", case]
    return subprocess.run(cmd, input=json.dumps(payload, ensure_ascii=False),
                          capture_output=True, text=True)


def test_案卷材料_草稿落案卷零入账(tmp_path):
    r = _tree(tmp_path)
    p = _draft(r, "域/x域/类/甲/方法/办", "c1",
               [{"路径": "域意.md", "内容": "域名: d9\n"}])
    assert p.returncode == 0, p.stderr
    f = os.path.join(r, "实例/甲/c1/域意.md")
    assert open(f, encoding="utf-8").read() == "域名: d9\n"
    assert not os.path.exists(os.path.join(r, "实例/甲/c1/__账")), "起草零入账"
    assert not os.path.exists(os.path.join(r, "域/d9")), "案卷材料不进正树"


def test_草稿源抄录免重打(tmp_path):
    r = _tree(tmp_path)
    p = _draft(r, "域/x域/类/甲/方法/办", "c1",
               [{"路径": "域意2.md", "源": "域.md"}])
    assert p.returncode == 0, p.stderr
    assert open(os.path.join(r, "实例/甲/c1/域意2.md"),
                encoding="utf-8").read().startswith("---\n域主:"), "源=案卷草稿抄录"


def test_产物槽落位_审批前半步(tmp_path):
    r = _tree(tmp_path)
    p = _draft(r, "域/x域/类/甲/方法/办", "c1",
               [{"路径": "域/d9/域.md", "源": "域.md"}])
    assert p.returncode == 0, p.stderr
    tp = os.path.join(r, "域", "d9", "域.md")
    assert open(tp, encoding="utf-8").read().startswith("---\n域主:"), \
        "产物槽落位（内容记号代入后恰为本任务产物弧）"
    assert not os.path.exists(os.path.join(r, "实例/甲/c1/__账")), "落位零入账"


def test_api写桥_draft透传stdin(tmp_path):
    r = _tree(tmp_path)
    p = _draft(r, "域/x域/类/甲/方法/办", "c1",
               [{"路径": "域意.md", "内容": "经写桥\n"}], api=True)
    assert p.returncode == 0, p.stderr
    assert open(os.path.join(r, "实例/甲/c1/域意.md"),
                encoding="utf-8").read() == "经写桥\n"


def test_树目标非产物槽_拒(tmp_path):
    r = _tree(tmp_path)
    p = _draft(r, "域/x域/类/甲/方法/办", "c1",
               [{"路径": "域/别家/域.md", "内容": "x"}])
    assert p.returncode != 0
    assert not os.path.exists(os.path.join(r, "域", "别家")), "零副作用"


def test_路径注入各形_拒(tmp_path):
    r = _tree(tmp_path)
    for bad in ("../逃.md", "a/../../逃.md", "/abs.md", "a\\b.md",
                ".隐藏.md", "__账/x.json", "a/..md"):
        p = _draft(r, "域/x域/类/甲/方法/办", "c1",
                   [{"路径": bad, "内容": "x"}])
        assert p.returncode != 0, bad
    assert not os.path.exists(os.path.join(str(tmp_path), "逃.md"))


def test_案卷越界与脏案卷号_拒(tmp_path):
    r = _tree(tmp_path)
    p = _draft(r, "域/x域/类/甲/方法/办", "../../pwn",
               [{"路径": "x.md", "内容": "x"}])
    assert p.returncode != 0
    p = _draft(r, "域/x域/类/甲/方法/办", None,
               [{"路径": "x.md", "内容": "x"}])
    assert p.returncode != 0, "无 --case 拒（草稿落案卷）"


def test_封存类_起草拒(tmp_path):
    r = _tree(tmp_path)
    _mk(r, "域/x域/类/甲/封存.md", "---\n封存: 真\n---\n")
    p = _draft(r, "域/x域/类/甲/方法/办", "c1",
               [{"路径": "域意.md", "内容": "x"}])
    assert p.returncode != 0
    assert "封存" in (p.stderr or p.stdout)
    assert not os.path.exists(os.path.join(r, "实例/甲/c1/域意.md"))


def test_载荷不是数组_拒(tmp_path):
    r = _tree(tmp_path)
    p = _draft(r, "域/x域/类/甲/方法/办", "c1", {"路径": "x.md"})
    assert p.returncode != 0


# ── 对抗验收修复钉（8-20 四镜头证伪后补）─────────────────

def _settle(r, case):
    """给 办 站办一本账（产物 域/d9/域.md 已在场时入账）。"""
    import subprocess as _sp
    _mk(r, "域/d9/域.md", "---\n域主: 张三\n---\n正式产物\n")
    tdir = os.path.join(r, "域/x域/类/甲/方法/办")
    return _sp.run([sys.executable, ENGINE, "backfill", tdir,
                    "--root", r, "--case", case, "--note", "测试办结"],
                   capture_output=True, text=True)


def test_落位禁区_已入账产物拒(tmp_path):
    """draft 不得覆写已办结入账的活产物（覆写+再办结=洗账面）。"""
    r = _tree(tmp_path)
    p = _settle(r, "c1")
    assert p.returncode == 0, p.stderr
    原文 = open(os.path.join(r, "域/d9/域.md"), encoding="utf-8").read()
    q = _draft(r, "域/x域/类/甲/方法/办", "c1",
               [{"路径": "域/d9/域.md", "内容": "被篡改\n"}])
    assert q.returncode != 0
    assert "活产物" in (q.stdout + q.stderr)
    assert open(os.path.join(r, "域/d9/域.md"),
                encoding="utf-8").read() == 原文, "零副作用"


def test_落位禁区_宪法时刻基线拒(tmp_path):
    """基线立案的产物槽不许起草面落位改写（手术面变更走女娲案卷）。"""
    r = _tree(tmp_path)
    _mk(r, "域/治理域/类/女娲/类.md", "---\ni3dna: 类\n---\n")
    _mk(r, "域/治理域/类/女娲/知识/宪法时刻.md",
        "| 路径 | sha256 |\n|---|---|\n"
        "| 域/d9/域.md | " + "0" * 64 + " |\n")   # 基线行=办站的产物槽
    q = _draft(r, "域/x域/类/甲/方法/办", "c1",
               [{"路径": "域/d9/域.md", "源": "域.md"}])
    assert q.returncode != 0
    assert "基线" in (q.stdout + q.stderr)
    assert not os.path.exists(os.path.join(r, "域/d9")), "零副作用"


def test_符号链接逃逸_拒(tmp_path):
    """案卷内预置符号链接不得把草稿写出案卷（词法包含性不够）。"""
    r = _tree(tmp_path)
    os.symlink(os.path.join(r, "状态"), os.path.join(r, "实例/甲/c1/链接"))
    q = _draft(r, "域/x域/类/甲/方法/办", "c1",
               [{"路径": "链接/逃逸.md", "内容": "x"}])
    assert q.returncode != 0
    assert not os.path.exists(os.path.join(r, "状态/逃逸.md")), "零副作用"


def test_载荷各坏形_拒且零副作用(tmp_path):
    r = _tree(tmp_path)
    bads = [
        [{"路径": 123, "内容": "x"}],              # 路径非字符串（曾裸崩）
        [{"路径": ["a", "b.md"], "内容": "x"}],
        [{"路径": "x.md"}],                        # 缺 内容/源
        [{"路径": "x.md", "源": "不在场.md"}],
        ["不是对象"],
        [{"路径": "x%d.md" % i, "内容": "x"} for i in range(21)],  # 超上限
    ]
    for bad in bads:
        p = _draft(r, "域/x域/类/甲/方法/办", "c1", bad)
        assert p.returncode != 0, bad
        assert "Traceback" not in (p.stderr or ""), "须干净拒不裸崩：%r" % (bad,)
    left = os.listdir(os.path.join(r, "实例/甲/c1"))
    assert sorted(left) == ["域.md", "申请.md"], left


def test_同方法他案卷办结同一产物_拒(tmp_path):
    """一案卷一手术·机械面：同方法对同一产物文件双案卷办结=后账覆盖
    洗账面（8-20 对抗验收），第二本拒。"""
    r = _tree(tmp_path)
    _mk(r, "实例/甲/c2/申请.md", "---\n域名: d9\n---\n申请。\n")
    p = _settle(r, "c1")
    assert p.returncode == 0, p.stderr
    q = _settle(r, "c2")          # 同方法、c2 案卷、办结同一 域/d9/域.md
    assert q.returncode != 0
    assert "一案卷一手术" in (q.stdout + q.stderr)
    assert not os.path.exists(os.path.join(
        r, "实例/甲/c2/__账/办/__结果.json")), "零副作用未入账"


def test_弧路径越出树根_按不可解析拒(tmp_path):
    """弧声明带 ../ 段不得把产物写出树根（8-20 对抗验收：改弧产物改写
    后经 fire 落树外）——resolve 复检按不可解析处理，fire 拒执行。"""
    r = _tree(tmp_path)
    _mk(r, "域/x域/类/甲/方法/逃/任务.md", """---
i3dna: 微任务
输入:
  - "{实例}/申请.md"
产物:
  - "../../树外.md"
---
坏弧。
""")
    tdir = os.path.join(r, "域/x域/类/甲/方法/逃")
    import subprocess as _sp
    p = _sp.run([sys.executable, ENGINE, "preflight", tdir,
                 "--root", r, "--case", "c1"],
                capture_output=True, text=True)
    assert "越出树根" in (p.stdout + p.stderr), "复检警告须出现"
    f = _sp.run([sys.executable, ENGINE, "run", tdir,
                 "--root", r, "--case", "c1", "--io", "stdout",
                 "--engine", "cat"],
                capture_output=True, text=True)
    assert f.returncode != 0, "fire 须拒（产物全部不可写）"
    assert not os.path.exists(os.path.join(str(tmp_path), "..", "树外.md"))


# ── 起草自举（8-20 真用例「给女娲加撤域」：内容记号任务空案卷死锁）──

MARK = """---
i3dna: 微任务
执行者: 人
输入:
  - "{实例}/申请.md"
产物:
  - "域/{申请.域}/类/{申请.类名}/方法/{申请.方法名}/任务.md"
---
加方法（内容记号产物弧）。
"""


def test_起草自举_内容记号缺申请不炸(tmp_path):
    """往空案卷起草 申请.md 正是 draft 的使命——load 不得在内容记号解析
    处死锁（真用例：给女娲加撤域方法，第一句就被拒「载荷缺失」）。"""
    r = _tree(tmp_path)
    _mk(r, "域/x域/类/甲/方法/加法/任务.md", MARK)
    os.makedirs(os.path.join(r, "实例/甲/c2"))          # 空案卷：无申请
    p = _draft(r, "域/x域/类/甲/方法/加法", "c2",
               [{"路径": "申请.md",
                 "内容": "---\n域: x域\n类名: 甲\n方法名: 新法\n---\n申请。\n"}])
    assert p.returncode == 0, p.stderr
    assert os.path.isfile(os.path.join(r, "实例/甲/c2/申请.md")), "申请落案卷"
    assert not os.path.exists(os.path.join(r, "实例/甲/c2/__账")), "起草零入账"


def test_起草自举_申请在场后落位照旧严格(tmp_path):
    """批准半步：申请在场→内容记号解析→落位只许产物弧（严面不动）。"""
    import subprocess as _sp
    r = _tree(tmp_path)
    _mk(r, "域/x域/类/甲/方法/加法/任务.md", MARK)
    os.makedirs(os.path.join(r, "实例/甲/c2"))
    _draft(r, "域/x域/类/甲/方法/加法", "c2",
           [{"路径": "申请.md",
             "内容": "---\n域: x域\n类名: 甲\n方法名: 新法\n---\n申请。\n"},
            {"路径": "任务.md", "内容": "---\ni3dna: 微任务\n---\n新法。\n"}])
    p = _draft(r, "域/x域/类/甲/方法/加法", "c2",
               [{"路径": "域/x域/类/甲/方法/新法/任务.md", "源": "任务.md"}])
    assert p.returncode == 0, p.stderr
    assert os.path.isfile(os.path.join(
        r, "域/x域/类/甲/方法/新法/任务.md")), "落位产物弧（记号已代申请值）"
    q = _draft(r, "域/x域/类/甲/方法/加法", "c2",
               [{"路径": "域/x域/类/甲/方法/别家/任务.md", "源": "任务.md"}])
    assert q.returncode != 0, "非本任务产物弧仍拒"
    # 严格面回归：fire/preflight 在申请缺席时照旧响亮拒（载荷缺失）
    f = _sp.run([sys.executable, ENGINE, "preflight",
                 os.path.join(r, "域/x域/类/甲/方法/加法"),
                 "--root", r, "--case", "c3"], capture_output=True, text=True)
    assert "载荷缺失" in (f.stdout + f.stderr) or "内容记号" in (f.stdout + f.stderr)


# ── 对抗评审三小修（工单108：F1 原子落位 / F3 案卷材料槽家族门）──

def test_F1_落位原子_并发两draft不互撕(tmp_path):
    """F1：pid 暂存＋os.replace（§8.1 同型）——两 draft 并发写同一产物槽，
    盘上终态必是其中一份的完整内容，无半截互撕、无 tmp 残留。"""
    r = _tree(tmp_path)
    tdir = os.path.join(r, "域/x域/类/甲/方法/办")
    a, b = "甲" * 50000, "乙" * 50000
    payloads = [json.dumps([{"路径": "域/d9/域.md", "内容": body}])
                for body in (a, b)]
    ps = [subprocess.Popen(
              [sys.executable, ENGINE, "draft", tdir,
               "--root", r, "--case", "c1"],
              stdin=subprocess.PIPE, stdout=subprocess.PIPE,
              stderr=subprocess.PIPE, text=True)
          for _ in payloads]
    outs = [p.communicate(input=pl) for p, pl in zip(ps, payloads)]
    for p, (_o, e) in zip(ps, outs):
        assert p.returncode == 0, e[-400:]
    tp = os.path.join(r, "域", "d9", "域.md")
    got = open(tp, encoding="utf-8").read()
    assert got in (a, b), "终态必是某一整份（原子换入，无撕裂）"
    assert not [f for f in os.listdir(os.path.dirname(tp)) if ".tmp." in f], \
        "暂存件随 replace 清场"


def test_F3_案卷材料槽家族_拒(tmp_path):
    """F3：案卷材料不得伪造消息/状态槽——伪单在场欺骗使能（开发见返工单
    ＝进修复模式），结账被悬账门拦死、案例卡死。路径段与名中类型（去 __ 段
    寻种，含顺号后缀形）两判据都拦；正常材料与产物槽分支照旧放行。"""
    r = _tree(tmp_path)
    _mk(r, "消息/返工单.md", "---\ni3dna: 消息\n---\n返工单种。\n")
    _mk(r, "消息/说明.md", "纯正文说明，无 frontmatter——不算类型。\n")
    cdir = os.path.join(r, "实例/甲/c1")
    for bad in ("测试/返工单.md",              # 名中消息类型名
                "测试/返工单__X__r2.md",       # 顺号后缀形剥段仍中
                "测试/消息/单.md",             # 嵌套槽家族路径段（首段形早被
                "测试/状态/状态.json"):        # TREE_TOPS 产物槽门拦，此处钉嵌套形）
        p = _draft(r, "域/x域/类/甲/方法/办", "c1",
                   [{"路径": bad, "内容": "伪造\n"}])
        assert p.returncode != 0, bad
        assert "槽家族" in (p.stdout + p.stderr), bad
        assert not os.path.exists(os.path.join(cdir, *bad.split("/"))), \
            "零副作用"
    q = _draft(r, "域/x域/类/甲/方法/办", "c1",
               [{"路径": "域意.md", "内容": "域名: d9\n"}])
    assert q.returncode == 0, q.stderr          # 正常案卷材料照旧
    w = _draft(r, "域/x域/类/甲/方法/办", "c1",
               [{"路径": "域/d9/域.md", "源": "域.md"}])
    assert w.returncode == 0, w.stderr          # 产物槽分支不受 F3 影响


def test_F2_journal留尸_两笔可diff_零账_裸树静默(tmp_path):
    """F2（工单109·裁定②）：draft 零入账、journal 留尸——同槽两稿两笔
    提交（scoped add 只加草稿不吞全树），git show 两具尸即换稿铁证；
    __账 零新增；非 git 裸树静默成功。"""
    import subprocess as _sp
    r = _tree(tmp_path)                          # 裸树：fail-soft 静默成功
    q = _draft(r, "域/x域/类/甲/方法/办", "c1",
               [{"路径": "域意.md", "内容": "一稿\n"}])
    assert q.returncode == 0, q.stderr
    assert not os.path.exists(os.path.join(r, ".git"))

    g = _tree(tmp_path / "g")
    for args in (["init", "-q"], ["config", "user.email", "t@t"],
                 ["config", "user.name", "t"]):
        _sp.run(["git", "-C", g] + args, capture_output=True, timeout=30)
    p1 = _draft(g, "域/x域/类/甲/方法/办", "c1",
                [{"路径": "域意.md", "内容": "第一稿\n"}])
    assert p1.returncode == 0, p1.stderr
    p2 = _draft(g, "域/x域/类/甲/方法/办", "c1",
                [{"路径": "域意.md", "内容": "第二稿（换稿）\n"}])
    assert p2.returncode == 0, p2.stderr
    logs = _sp.run(["git", "-C", g, "log", "--format=%s"],
                   capture_output=True, text=True).stdout.splitlines()
    drafts = [m for m in logs if m.startswith("起草")]
    assert len(drafts) == 2, logs               # 两稿两笔 journal
    assert all("c1" in m for m in drafts), "message 含案卷号"
    rel = "实例/甲/c1/域意.md"
    v1 = _sp.run(["git", "-C", g, "show", f"HEAD~1:{rel}"],
                 capture_output=True, text=True).stdout
    v2 = _sp.run(["git", "-C", g, "show", f"HEAD:{rel}"],
                 capture_output=True, text=True).stdout
    assert "第一稿" in v1 and "第二稿" in v2, "两具尸——换稿 git diff 可证"
    tracked = _sp.run(["git", "-C", g, "-c", "core.quotepath=off",
                       "ls-files"],
                      capture_output=True, text=True).stdout.split()
    assert tracked == [rel], tracked            # scoped add：不代别人提交在途文件
    assert not os.path.exists(os.path.join(g, "实例/甲/c1/__账")), "零账保持"
