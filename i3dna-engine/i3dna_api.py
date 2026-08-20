#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""i3dna_api — 目录体系的 Agent API（读桥 JSON 面 + 写桥直通引擎）。

不擅长操作界面的 agent（LLM/脚本/CI）从这里与目录体系交互：
- **读桥**（tree/tasks/task/account/lint/coverage）：本进程直算，一律
  JSON 出 stdout——引擎 CLI 的人读格式不重复造；拒绝也机读
  （{拒绝: 理由} + 退出码 2，记号缺值/取值失败照旧响亮）。
- **写桥**（fire/settle/advance/login）：不另起灶，subprocess 直通
  i3dna_engine.py 对应动词（run/backfill/converge/login）——引擎仍是
  唯一写路径，暂存-验收-落位-账纪律原样透传，stdout/退出码原样给出。

动词：
  读  tree <根>                      域/类(含方法·关系边)/场所拓扑
      tasks <根> [--task 相对路径]   任务清单（案卷们·执行者·色彩·校验门）
      task  <根> --task p [--case k] 弧解析预检（在场/可缺/回收/产物目标）
      account <根> [--task p] [--case k]             账本（判据面）
      lint   <根>                    lint 报告（退出码=有无错误）
      coverage <根>                  MBT 变迁/边覆盖（有缺口退 1，同引擎）
  写  fire   <根> --task p [--case k] [--engine e] [--executor 主体] …
      settle <根> --task p [--case k] [--note 备注]      → backfill
      draft  <根> --task p --case k  （stdin JSON：[{路径, 内容|源}]）
                                       → draft（101号 起草车道：草稿落案卷
                                         零入账；产物槽落位=审批前半步）
      advance <根> [--plan] [--max-rounds n]             → converge（全树）
      login  <根> --principal 主体值 [--status 状态]      → 登录入账

--task 一律树内相对路径（解析后落在树根之外=越界，{拒绝} 退 2——
树内绝对路径会被归一接受）。
例：python3 i3dna_api.py tasks ../md-devloop-m1
    python3 i3dna_api.py fire ../md-devloop-m1 \\
        --task 域/治理域/类/女娲/方法/立场所 --case 广州开发一部
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, rel):
    """按路径装载单一副本（explorer/core 同款纪律：不猜环境，装载即校准）。"""
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sys.modules[name] = m
    return m


eng = _load("i3dna_engine", "i3dna_engine.py")
mdl = _load("i3dna_model", "i3dna_model.py")
lint = _load("i3dna_lint", os.path.join("..", "i3dna-lint", "i3dna_lint.py"))

FM_RE = re.compile(r"^---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", re.S)


def _emit(obj, code=0):
    if hasattr(sys.stdout, "reconfigure"):        # 输出钉 UTF-8，locale 无关
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))
    sys.exit(code)


def _rel(p, root):
    return None if p is None else os.path.relpath(p, root)


def _in_root(root, task_rel):
    """--task 归一为树内相对路径；越界（../ 或绝对路径）响亮拒绝。"""
    p = os.path.normpath(os.path.join(root, os.path.normpath(task_rel)))
    if p != root and not p.startswith(root + os.sep):
        _emit({"拒绝": f"任务路径越出树根：{task_rel}"}, 2)
    return os.path.relpath(p, root)


def _task_abs(root, task_rel):
    """--task → 树内绝对路径；normpath 归一（./ 与尾斜杠），越界响亮拒绝。"""
    if not task_rel:
        return None
    return os.path.join(root, _in_root(root, task_rel))


def _fm_of(text):
    """frontmatter（锚定首对 ---，非映射内容不算）→ dict。"""
    m = FM_RE.match(text)
    if not m:
        return {}
    try:
        y = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}
    return y if isinstance(y, dict) else {}


def _任务文(tdir):
    md = os.path.join(tdir, "任务.md")
    if os.path.isfile(md):
        return open(md, encoding="utf-8", errors="replace").read()
    import glob
    alt = sorted(glob.glob(os.path.join(tdir, "__*任务定义*.md")))
    return open(alt[0], encoding="utf-8", errors="replace").read() if alt else ""


# ── 读桥动词 ──────────────────────────────────────────────

def api_tree(root):
    t = mdl.树根(root)
    out = {"根": root, "域": [], "类": [], "场所": []}
    for d in t.域们():
        out["域"].append({"名": d.名, "路径": _rel(d.path, root),
                          "域主": d.域主, "职责": d.职责})
    for c in t.类们():
        entry = {"名": c.名, "路径": _rel(c.path, root),
                 "范畴": "过程" if isinstance(c, mdl.过程类) else "实体",
                 "关系": [{"类型": e.类型, "方向": e.方向, "种": e.种}
                          for e in c.关系们()]}
        if isinstance(c, mdl.过程类):
            entry["方法"] = [{"名": m.名, "路径": _rel(m.path, root),
                              "执行者": m.执行者声明, "色": m.色}
                             for m in c.方法们()]
        out["类"].append(entry)
    for s in t.场所们():
        out["场所"].append({"名": s.名, "种": s.种, "是根场所": s.是根场所,
                            "类集": [c.名 for c in s.类集()],
                            "锚": _rel(s.锚路径, root)})
    _emit(out)


def _task_cases(root, tdir):
    """案卷们——与引擎 _account_candidates 同判定：{实例}/{案卷号} 记号
    都算 marked（跨架弧），案卷架=实例/<类名>/* 一级目录；类级=[None]。"""
    if "{实例}" not in (body := _任务文(tdir)) \
            and "{案卷号}" not in body:
        return [None]
    kr = eng.klass_rel(tdir, root)
    shelf = os.path.join(root, "实例", os.path.basename(kr)) \
        if kr else os.path.join(root, "实例")
    if not os.path.isdir(shelf):
        return []
    return sorted(k for k in os.listdir(shelf)
                  if os.path.isdir(os.path.join(shelf, k))
                  and not k.startswith("."))


def _task_meta(root, tdir, kind):
    fm = _fm_of(_任务文(tdir))
    kr = eng.klass_rel(tdir, root)
    return {"路径": _rel(tdir, root), "底物族": kind,
            "类": kr,
            "封存": bool(kr and os.path.isfile(
                os.path.join(root, kr, "封存.md"))),
            "执行者": fm.get("执行者"), "校验": fm.get("校验"),
            "色": "红" if os.path.isdir(os.path.join(tdir, "执行程序"))
                  else ("绿" if fm.get("执行者") == "人" else "蓝"),
            "案卷们": _task_cases(root, tdir)}


def api_tasks(root, task_rel):
    want = _in_root(root, task_rel) if task_rel else None
    out = {"根": root, "任务": []}
    for tdir, kind in sorted(eng.find_tasks(root).items()):
        if want and _rel(tdir, root) != want:
            continue
        out["任务"].append(_task_meta(root, tdir, kind))
    if want and not out["任务"]:
        _emit({"拒绝": f"任务不存在：{task_rel}"}, 2)
    _emit(out)


def api_task(root, task_rel, case):
    tdir = _task_abs(root, task_rel)
    if not os.path.isdir(tdir):
        _emit({"拒绝": f"任务不存在：{task_rel}"}, 2)
    try:
        t = eng.load_task(tdir, root, case=case)
    except SystemExit as e:
        _emit({"拒绝": str(e), "任务": task_rel, "案卷": case}, 2)
    rows = []
    for r in t["rows"]:
        rows.append({"弧": r["kind"], "名": r["pname"], "注": r.get("desc"),
                     "路径": _rel(r["path"], root) if r.get("path") else None,
                     "在场": bool(r.get("path") and os.path.exists(r["path"])),
                     "可缺": bool(r.get("optional")),
                     "回收": bool(r.get("retract"))})
    _emit({"任务": task_rel, "案卷": t.get("case"), "底物族": t.get("kind"),
           "执行者": t.get("executor"), "弧": rows})


def _find_tdir(root, cls, 方法名):
    """盘上反寻任务定义目录（账是盘面真值，定义可寻则给真路径）。"""
    import glob as g
    for pat in (os.path.join(root, "域", "*", "类", cls, "方法", 方法名),
                os.path.join(root, "类", cls, "方法", 方法名)):
        hit = sorted(g.glob(pat))
        if hit:
            return hit[0]
    return None


def api_account(root, task_rel, case):
    """账本（判据面）——盘直读，不经任务定义：案卷账=实例/<类>/<案卷>/__账/
    <方法>/，类级账=任务目录直挂。定义侧损坏不吞已点火的账（账在盘上）；
    坏账/权限错误以「坏账」行露出，不崩栈不出假审计结论。"""
    import glob as g
    want = _in_root(root, task_rel) if task_rel else None
    out = {"根": root, "账": []}

    def _read(rd, meta):
        try:
            rec = eng.load_account(rd, root)
        except (ValueError, OSError) as e:
            out.setdefault("坏账", []).append(
                {"账目录": _rel(rd, root), "原因": str(e)[:120]})
            return
        if rec:
            out["账"].append({**meta, "账目录": _rel(rd, root), "记录": rec})

    for acc in sorted(g.glob(os.path.join(root, "实例", "*", "*", "__账",
                                          "*", "__结果.json"))):
        rd = os.path.dirname(acc)
        方法名 = os.path.basename(rd)
        案卷 = os.path.basename(os.path.dirname(os.path.dirname(rd)))
        cls = os.path.basename(os.path.dirname(
            os.path.dirname(os.path.dirname(rd))))
        if case is not None and 案卷 != case:
            continue
        tdir = _find_tdir(root, cls, 方法名)
        if want and (tdir is None or _rel(tdir, root) != want):
            continue
        _read(rd, {"任务": _rel(tdir, root) if tdir else None,
                   "方法": 方法名, "案卷": 案卷})
    for tdir in sorted(eng.find_tasks(root)):         # 类级账：任务目录直挂
        if want and _rel(tdir, root) != want:
            continue
        _read(tdir, {"任务": _rel(tdir, root), "案卷": None})
    _emit(out)


def api_lint(root):
    rep = lint.lint_tree(root)
    _emit({"根": root,
           "错误": [{"处": w, "消息": m} for w, m in rep.errors],
           "警告": [{"处": w, "消息": m} for w, m in rep.warnings],
           "信息": [{"处": w, "消息": m} for w, m in rep.infos]},
          code=1 if rep.errors else 0)


def api_coverage(root):
    rep = eng.coverage_report(os.path.abspath(root))
    未点火 = [_rel(t, root) for t in rep["未点火"]]
    未走过 = [[_rel(u, root), _rel(v, root), _rel(p, root)]
             for u, v, p in rep["边"] if (u, v, p) not in rep["已走过"]]
    _emit({"根": root,
           "变迁覆盖": {"已点火": len(rep["已点火"]), "总数": len(rep["任务"]),
                        "未点火": 未点火},
           "边覆盖": {"已走过": len(rep["已走过"]), "总数": len(rep["边"]),
                      "未走过": 未走过}},
          code=1 if (未点火 or 未走过) else 0)     # 同引擎：有缺口退 1


# ── 写桥动词：直通引擎，stdout/退出码原样 ─────────────────

def _passthrough(verb, a, root, target):
    """直通引擎；target=引擎位置参数（advance=树根，fire/settle=任务绝对
    路径，login=主体值）；旗标按名透传（0 是值不是空，不吞）。"""
    cmd = [sys.executable, os.path.join(HERE, "i3dna_engine.py"), verb, target]
    for k, v in vars(a).items():
        if k in ("verb", "target", "task", "principal"):
            continue
        if v is None or v is False or (isinstance(v, str) and v == ""):
            continue
        flag = "--" + k.replace("_", "-")
        if v is True:
            cmd.append(flag)
        elif isinstance(v, list):
            for x in v:
                cmd += [flag, str(x)]
        else:
            cmd += [flag, str(v)]
    cmd += ["--root", root]
    sys.exit(subprocess.call(cmd))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("verb", choices=["tree", "tasks", "task", "account",
                                     "lint", "coverage",
                                     "fire", "settle", "draft", "advance",
                                     "login"])
    ap.add_argument("target", nargs="?", default=".",
                    help="树根（默认当前目录）")
    ap.add_argument("--task", help="任务相对路径（task/account/fire/settle 用）")
    ap.add_argument("--case", help="案卷号（{实例} 记号代入）")
    ap.add_argument("--principal", help="login 用：主体值（实例/人员/<姓名>）")
    ap.add_argument("--status", default="", help="login 用：登录事件状态")
    ap.add_argument("--engine", help="fire 用：引擎命令（默认 DEFAULT_ENGINE）")
    ap.add_argument("--executor", help="fire/settle 用：执行者覆盖（主体值）")
    ap.add_argument("--io", choices=["write", "stdout"], help="fire 用")
    ap.add_argument("--timeout", type=int, help="fire 用：秒")
    ap.add_argument("--note", default="", help="settle 用：备注（fire 不消费）")
    ap.add_argument("--intent", default="",
                    help="fire/settle/advance 用：意图入账（101号 右键对话"
                         "——话语原文，账记「意图」字段，不参与 sha 对账）")
    ap.add_argument("--sandbox", help="fire 用：沙盒根")
    ap.add_argument("--run_id", default="", help="fire 用：批次标识")
    ap.add_argument("--stream", action="store_true", help="fire 用：流式过程")
    ap.add_argument("--plan", action="store_true", help="advance 用：只列计划")
    ap.add_argument("--max_rounds", type=int, help="advance 用：轮数上限")
    a = ap.parse_args()

    root = os.path.abspath(a.target)
    if not os.path.isdir(root):                    # 根不存在：统一机读拒绝
        _emit({"拒绝": f"树根不存在：{a.target}"}, 2)
    if a.verb == "task" and not a.task:
        _emit({"拒绝": "task 需要 --task 任务相对路径"}, 2)

    reads = {"tree": lambda: api_tree(root),
             "tasks": lambda: api_tasks(root, a.task),
             "task": lambda: api_task(root, a.task, a.case),
             "account": lambda: api_account(root, a.task, a.case),
             "lint": lambda: api_lint(root),
             "coverage": lambda: api_coverage(root)}
    if a.verb in reads:
        reads[a.verb]()
    elif a.verb == "login":
        if not a.principal:
            _emit({"拒绝": "login 需要 --principal 主体值"}, 2)
        _passthrough("login", a, root, a.principal)
    elif a.verb == "advance":                      # converge 吃树根不吃任务
        _passthrough("converge", a, root, root)
    else:                                          # fire/settle/draft
        if not a.task:
            _emit({"拒绝": f"{a.verb} 需要 --task 任务相对路径"}, 2)
        if a.verb == "draft" and not a.case:
            _emit({"拒绝": "draft 需要 --case 案卷号（草稿落案卷）"}, 2)
        _passthrough({"fire": "run", "settle": "backfill",
                      "draft": "draft"}[a.verb],
                     a, root, _task_abs(root, a.task))


if __name__ == "__main__":
    main()
