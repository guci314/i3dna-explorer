#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""i3dna_core —— explorer 的业务逻辑层（零 Qt）。

分层律：凡是「从树和账推导事实」的逻辑住这里——三色谱判定、类/实例
寻址、构造参数、待人办清单、实例 schema、工单文件事务、执行流折行
布局（纯几何）。界面（i3dna_explorer.py）只做渲染与事件，每个业务
函数都可无头 import 直测。引擎、lint 与 model 的装载也归本层（各自单一副本）。
"""
import glob
import importlib.util
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def _engine_home():
    """引擎家（engine/lint/model 与树所在的仓根）。explorer 已迁出独立
    安家（8-21：report_generate/i3dna-explorer → ~/work/explorer）：
    环境变量 I3DNA_HOME 优先；依赖内嵌 explorer 目录则认本目录
    （mint 布局：engine/lint/树住 ~/work/explorer 肚子里）；旧仓在场
    则认旧仓；都否回退上级（explorer 仍住仓内时行为逐字不变）。"""
    env = os.environ.get("I3DNA_HOME")
    if env:
        return env
    if os.path.isdir(os.path.join(HERE, "i3dna-engine")):
        return HERE
    old = os.path.expanduser(os.path.join("~", "work", "report_generate"))
    if os.path.isdir(os.path.join(old, "i3dna-engine")):
        return old
    return os.path.dirname(HERE)


BASE = _engine_home()


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


eng = _load("i3dna_engine", os.path.join(BASE, "i3dna-engine", "i3dna_engine.py"))
lint = _load("i3dna_lint", os.path.join(BASE, "i3dna-lint", "i3dna_lint.py"))
mdl = _load("i3dna_model", os.path.join(BASE, "i3dna-engine", "i3dna_model.py"))


# ── 三色谱 ───────────────────────────────────────────────────

def task_kind(tdir):
    """🔴 红＝符号程序在场、🟢 绿＝执行者:人、🔵 蓝＝其余（LLM）。
    演化方向：绿→蓝＝信息化，蓝→红＝符号化；
    逃逸通道：蓝→绿＝消息单据，红→蓝＝回退联结主义。"""
    if eng.exec_entry(tdir):
        return "红"
    if eng.get_value(os.path.join(tdir, "任务.md"), "执行者") == "人":
        return "绿"
    return "蓝"


# ── 类与实例寻址 ─────────────────────────────────────────────

def class_methods(croot):
    md = os.path.join(croot, "方法")
    if not os.path.isdir(md):
        return []
    return [os.path.join(md, d) for d in sorted(os.listdir(md))
            if os.path.isfile(os.path.join(md, d, "任务.md"))]


def case_dir(root, croot, case):
    """实例库寻址（与引擎 case_rel 同规则）：实例/<类名>/<k>；
    类根＝树根的单类树退化为 实例/<k>。"""
    kr = os.path.relpath(croot, root)
    shelf = [os.path.basename(kr)] if kr != "." else []
    return os.path.join(root, "实例", *shelf, case)


def ctor_params(root, croot):
    """构造参数**声明制**：状态类型 `定型:` 含「实例化人」者即构造参数
    （类根先于企业根，同名遮蔽）。无任何声明时回退旧推导（供给缺口法）。"""
    declared, seen = [], set()
    for sdir in (os.path.join(croot, "状态"), os.path.join(root, "状态")):
        if not os.path.isdir(sdir):
            continue
        for f in sorted(os.listdir(sdir)):
            if not f.endswith(".md") or f[:-3] in seen:
                continue
            seen.add(f[:-3])
            fp = os.path.join(sdir, f)
            mold, path = eng.get_value(fp, "定型"), eng.get_value(fp, "路径")
            if not mold or not path or "实例化人" not in str(mold):
                continue
            rel = str(path)
            if eng.CASE_MARK in rel:
                declared.append(rel.split(eng.CASE_MARK + "/", 1)[-1])
    if declared:
        return sorted(set(declared))
    # 回退：机械推导——被消费、无人产出、必需、实例作用域的输入。
    ins, prods = [], set()
    for t in class_methods(croot):
        human = eng.get_value(os.path.join(t, "任务.md"), "执行者") == "人"
        rows, _ = eng._frontmatter_rows(os.path.join(t, "任务.md"))
        for r in rows:
            rel = (r["pdir"] + "/" if r["pdir"] not in ("", "*") else "") \
                + r["pname"]
            if eng.CASE_MARK not in rel:
                continue
            rel = rel.split(eng.CASE_MARK + "/", 1)[-1]
            if r["kind"] == "产物":
                if not human:          # 人工工位产物不算供给源（防自举空实例）
                    prods.add(rel)
            elif not r.get("optional"):
                ins.append(rel)
    return sorted({r for r in ins if r not in prods})


def missing_state_slots(croot, cdir):
    """裸建实例缺的字段区文件清单（补播菜单的判据）。"""
    ent = os.path.dirname(os.path.dirname(croot))
    out = []
    for b in (croot, ent):
        for tf in glob.glob(os.path.join(b, "状态", "*.md")):
            law = eng.get_value(tf, "路径")
            if not law:
                continue
            rel = str(law).split(eng.CASE_MARK + "/", 1)[-1]
            if not os.path.isfile(os.path.join(cdir, rel)) and rel not in out:
                out.append(rel)
    return out


# ── 待人办（绿任务）─────────────────────────────────────────

def pending_human(root, croot, case):
    """本实例的待人办清单（🧑 工位且 LHS 满足）。"""
    out = []
    for t in class_methods(croot):
        try:
            _, reason = eng._task_needs_fire(t, root, case)
        except SystemExit:
            continue
        if reason.startswith("待人办"):
            out.append((t, reason))
    return out


def task_pending_cases(root, tdir, limit=8):
    """正在等这个工位的实例清单（同类实例逐个问 needs_fire）。"""
    croot = os.path.dirname(os.path.dirname(tdir))
    shelf = os.path.join(root, "实例", os.path.basename(croot))
    if not os.path.isdir(shelf):
        shelf = os.path.join(root, "实例")
    out = []
    for d in sorted(glob.glob(os.path.join(shelf, "*"))):
        name = os.path.basename(d)
        if not os.path.isdir(d) or name.startswith((".", "__")):
            continue
        try:
            _, reason = eng._task_needs_fire(tdir, root, name)
        except SystemExit:
            continue
        if reason.startswith("待人办"):
            out.append(name)
        if len(out) >= limit:
            break
    return out


# ── 实例 schema（类结构推导）────────────────────────────────

def class_schema(croot):
    """槽位并集（从方法弧机械推导）join 消息/状态类型声明。
    返回（逐槽显示行, 未立类型声明的可缺消息清单）——渲染归界面。"""
    ent = os.path.dirname(os.path.dirname(croot))
    slots = {}
    for t in class_methods(croot):
        name = os.path.basename(t)
        human = eng.get_value(os.path.join(t, "任务.md"), "执行者") == "人"
        rows, _ = eng._frontmatter_rows(os.path.join(t, "任务.md"))
        for r in rows:
            rel = (r["pdir"] + "/" if r["pdir"] not in ("", "*") else "") \
                + r["pname"]
            if eng.CASE_MARK not in rel:
                continue
            rel = rel.split(eng.CASE_MARK + "/", 1)[-1]
            d = slots.setdefault(rel, {"prod": [], "cons": [], "opt": False,
                                       "cond": None, "prod_auto": False})
            if r["kind"] == "产物":
                d["prod"].append(name + ("🧑" if human else ""))
                d["prod_auto"] = d["prod_auto"] or not human
            else:
                d["cons"].append(name)
            d["opt"] = d["opt"] or bool(r.get("optional"))
            d["cond"] = d["cond"] or r.get("cond")
    out = []
    for rel in sorted(slots):
        d = slots[rel]
        tname = os.path.splitext(os.path.basename(rel))[0] + ".md"
        tp, mf, sf = "", None, None
        for base_dir, tag in ((croot, ""), (ent, "·继承")):
            m0 = os.path.join(base_dir, "消息", tname)
            s0 = os.path.join(base_dir, "状态", tname)
            if mf is None and os.path.isfile(m0):
                mf = m0
            if sf is None and os.path.isfile(s0):
                sf = (s0, tag)
        if mf:
            keys = eng.get_value(mf, "键")
            tp = (f"键 {keys}｜发 {eng.get_value(mf, '发送方')}"
                  f"→收 {eng.get_value(mf, '接收方')}")
        elif sf:
            s0, tag = sf
            keys = eng.get_value(s0, "键")
            tp = (f"{eng.get_value(s0, '性质') or ''}"
                  + (f"｜键 {keys}" if keys else "") + tag)
        elif not d["prod_auto"]:
            tp = "构造参数（实例化时人给）"
        if mf:
            nature = "消息"
        elif sf:
            nature = "常驻状态"
        else:                    # 未立类型声明：按可缺旗标近似（弧推导）
            nature = "消息·可缺" if d["opt"] else "常驻状态"
        out.append({"槽": rel,
                    "生产": "、".join(d["prod"]) or "—",
                    "消费": "、".join(d["cons"]) or "—",
                    "性质": nature,
                    "使能": str(d["cond"] or "—"),
                    "类型": tp or "—"})
    undeclared = [r for r in slots
                  if slots[r]["opt"] and not os.path.isfile(
                      os.path.join(croot, "消息", os.path.basename(r)))]
    return out, undeclared


# ── 绿任务工单的文件事务 ─────────────────────────────────────

def workform_stub(task, r):
    """空交付的键表存根：类型声明的键（schema 共识）预填键侧，值留给人。"""
    tf = (eng._type_file(task, r, "状态")
          or eng._type_file(task, r, "消息"))
    keys = eng.get_value(tf, "键") if tf else None
    if isinstance(keys, list) and keys:
        return "---\n" + "\n".join(f"{k}: " for k in keys) + "\n---\n\n"
    return ""


def workform_apply(items):
    """办结的文件半边：写有变化的交付、开/销单。
    items＝[(row, mode, checked, text, orig)]，
    mode ∈ {doc, ticket_present, ticket_absent}。返回动作摘要。"""
    acts = []
    for r, mode, checked, txt, orig in items:
        p = r["path"]
        if not p:
            continue
        if mode == "ticket_present":
            if checked and os.path.isfile(p):
                os.remove(p)                   # 销单＝收回
                acts.append(f"销单 {r['pname']}")
            continue
        if mode == "ticket_absent":
            if not checked:
                continue
            if not txt.strip():
                # 零键消息的法定最小形态就是一枚 token（在场即信号）——
                # 勾了开单就必须落文件，空正文补最小体（8-11 评审 #5）
                txt = f"# {r['pname']}\n"
        if not txt.strip() or txt == orig:
            continue
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(txt if txt.endswith("\n") else txt + "\n")
        acts.append(("开单 " if mode == "ticket_absent" else "写 ")
                    + r["pname"])
    return acts


# ── 执行流布局（纯几何，零 Qt）──────────────────────────────

def gather_arcs(root, task_rows_all, show_ptr, pkg):
    """弧集：按包过滤（包=类名，见 _pkg_of；根级/旧式树退化为首段）；
    跳过 ↳ 两级展开行；指针库所默认隐藏。"""
    rows_f = {t: r for t, r in task_rows_all.items()
              if pkg == "全部" or _pkg_of(root, t) == pkg}
    arcs, places, opt_inputs = [], {}, set()
    for tdir, rows in rows_f.items():
        for r in rows:
            if not r["path"] or r["desc"].startswith("↳"):
                continue
            if not show_ptr and r["kind"] == "输入" \
                    and "索引文件" in r["pname"]:
                continue
            places.setdefault(r["path"], r["pname"])
            arcs.append((tdir, r["path"], r["kind"]))
            if r["kind"] == "输入" and r.get("optional"):
                opt_inputs.add((tdir, r["path"]))
    return rows_f, arcs, places, opt_inputs


def components(task_rows, arcs, root=None):
    """连通块（并查集），大块在前——不同包/不相干链分组画。
    企业共享件（根级知识/契约：relpath 不在 类/ 下且无 {实例} 记号）
    **不参与并线**——否则一份执行契约把所有类焊成一坨、标题张冠李戴；
    共享件事后补挂进每个引用它的组件（可重复出现）。"""
    def shared(p):
        if not root:
            return False
        rel = os.path.relpath(p, root)
        # 只把「根级共享件」（既不在 类/ 也不在 实例/ 下、且无 {实例} 记号）当共享；
        # 实例路径（实例/…）是实例视角解析出来的，必须参与并线，否则微任务会被拆散
        return (not rel.startswith("类" + os.sep)
                and not rel.startswith("实例" + os.sep)
                and eng.CASE_MARK not in rel)

    par = {}

    def find(x):
        par.setdefault(x, x)
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for t, p, _ in arcs:
        if shared(p):
            continue
        par[find(t)] = find(p)
    for t in task_rows:
        find(t)
    comps = {}
    for n in list(par):
        comps.setdefault(find(n), []).append(n)
    out = sorted(comps.values(), key=len, reverse=True)
    for c in out:                       # 共享件补挂（不并线只出席）
        ts = {n for n in c if n in task_rows}
        extra = {p for t, p, _k in arcs if t in ts and shared(p)}
        c.extend(sorted(extra - set(c)))
    return out


def layout_component(cnodes, task_rows, places, arcs, opt_inputs,
                     viewport_w, y_base, COL=210, ROW=72):
    """折行布局（打字机式）：分层→列→按视口宽度折段，段内左→右。
    可选弧不参与分层（反馈环会把列号推上天）。纯几何，零 Qt。
    返回 (pos, comp_h, carcs, cplaces)。"""
    ctasks = [n for n in cnodes if n in task_rows]
    cplaces = [n for n in cnodes if n in places]
    if not ctasks:
        return {}, 0, [], []
    carcs = [(t, p, k) for t, p, k in arcs if t in ctasks]
    prod = {p: t for t, p, k in carcs if k == "产物"}
    level = {t: 0 for t in ctasks}
    for _ in range(len(ctasks) + 1):
        for t, p, k in carcs:
            if k == "输入" and p in prod and prod[p] != t \
                    and (t, p) not in opt_inputs:
                level[t] = max(level[t], level[prod[p]] + 1)
    col = {t: level[t] * 2 for t in ctasks}
    for p in cplaces:
        cons = [level[t] for t, q, k in carcs if q == p and k == "输入"]
        col[p] = level[prod[p]] * 2 + 1 if p in prod \
            else (min(cons) * 2 - 1 if cons else 0)
    shift = -min(col.values())
    for n in col:
        col[n] += shift
    neigh = {}
    for t, p, _k in carcs:
        neigh.setdefault(t, []).append(p)
        neigh.setdefault(p, []).append(t)
    pos, rowpos = {}, {}
    K = max(4, int(viewport_w) // COL)
    colset = sorted(set(col.values()))
    # 小图不折行：总列数不多时宁可横向缩放，也不折段——折段会把「左→右的
    # 流程关系」拦腰截成上下两排。列号有跳空（任务偶数位、制品奇数位），
    # 用 max(colset)+1 才是真实列数（len(colset) 会把 col4 折进第二排）。
    if colset and max(colset) + 1 <= 8:
        K = max(K, max(colset) + 1)
    per_col = {}
    for c in colset:
        nodes = [n for n in col if col[n] == c]
        nodes.sort(key=lambda n: (
            sum(rowpos.get(m, 0) for m in neigh.get(n, [])) /
            max(1, len([m for m in neigh.get(n, []) if m in rowpos])),
            str(n)))
        per_col[c] = nodes
        for i, n in enumerate(nodes):
            rowpos[n] = i
    band_rows = {}
    for c in colset:
        band_rows[c // K] = max(band_rows.get(c // K, 0), len(per_col[c]))
    band_y, acc = {}, y_base + 36
    for b in sorted(band_rows):
        band_y[b] = acc
        acc += band_rows[b] * ROW + 56
    for c in colset:
        for n in per_col[c]:
            pos[n] = ((c % K) * COL, band_y[c // K] + rowpos[n] * ROW)
    return pos, acc - y_base, carcs, cplaces


def task_flow_arcs(arcs, opt_inputs=None):
    """折叠制品，得「任务→任务」的流程弧 [(上游, 下游, 中间制品, 是否经可缺弧), ...]。
    同一个制品把上游、下游直接连起来——微任务之间不再被制品节点隔开。
    只认**单一生产者**的制品为流程弧：多生产者（状态.json 之类共享字段区）
    不是流程传递，跳过——否则共享状态会把所有任务焊成环、流程层次推上天。"""
    opt_inputs = opt_inputs or set()
    prod = {}
    for t, p, k in arcs:
        if k == "产物":
            prod.setdefault(p, []).append(t)
    out = []
    for t, p, k in arcs:
        if k == "输入" and p in prod and t not in prod[p] \
                and len(prod[p]) == 1:
            out.append((prod[p][0], t, p, (t, p) in opt_inputs))
    return out


def task_flow_layout(tasks, tarcs, viewport_w, y_base, COL=210, ROW=72):
    """任务流程布局（零 Qt）：任务按 DAG 层从左到右，列=层*2，同列竖排（并行）。
    可缺弧不参与分层——反馈环（如 开发→澄清单→澄清需求）会把列号推上天。"""
    level = {t: 0 for t in tasks}
    for _ in range(len(tasks) + 1):
        for a, b, _p, opt in tarcs:
            if opt:
                continue
            level[b] = max(level[b], level[a] + 1)
    col = {t: level[t] * 2 for t in tasks}
    if col:
        shift = -min(col.values())
        for t in col:
            col[t] += shift
    pos, rowpos = {}, {}
    colset = sorted(set(col.values()))
    per_col = {}
    for c in colset:
        nodes = [t for t in col if col[t] == c]
        per_col[c] = nodes
        for i, n in enumerate(nodes):
            rowpos[n] = i
    K = max(4, int(viewport_w) // COL)
    if colset and max(colset) + 1 <= 8:
        K = max(K, max(colset) + 1)
    band_rows = {}
    for c in colset:
        band_rows[c // K] = max(band_rows.get(c // K, 0), len(per_col[c]))
    band_y, acc = {}, y_base + 36
    for b in sorted(band_rows):
        band_y[b] = acc
        acc += band_rows[b] * ROW + 56
    for c in colset:
        for n in per_col[c]:
            pos[n] = ((c % K) * COL, band_y[c // K] + rowpos[n] * ROW)
    return pos, acc - y_base


def lineage_entries(dirpath):
    """血缘(94号)读取:dirpath/__血缘.md → [{键,哈希,来源,时间,原始}, ...]。
    格式 键 :: 值哈希 :: 来源(案卷号/方法) :: 时间;坏行原样带回(键=?,原始)。
    无文件 → []。无头直测,UI 只读渲染。"""
    lf = os.path.join(dirpath, "__血缘.md")
    if not os.path.isfile(lf):
        return []
    out = []
    for ln in open(lf, encoding="utf-8", errors="replace").read().splitlines():
        if not ln.strip():
            continue
        parts = [p.strip() for p in ln.split("::")]
        if len(parts) == 4:
            out.append({"键": parts[0], "哈希": parts[1],
                        "来源": parts[2], "时间": parts[3], "原始": ln})
        else:
            out.append({"键": "?", "哈希": "", "来源": "", "时间": "", "原始": ln})
    return out


# ── 最近打开目录(文件菜单) ────────────────────────────────

RECENT_FILE = os.path.join(os.path.expanduser("~"), ".i3dna-explorer",
                           "recent.json")
RECENT_MAX = 10


def recent_roots_load(path=None):
    """最近打开目录清单(新→旧,上限 10,只留仍存在的目录)。损坏/缺失 → []。"""
    path = path or RECENT_FILE
    try:
        import json as _json
        data = _json.load(open(path, encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return [str(p) for p in data
                if isinstance(p, str) and os.path.isdir(p)][:RECENT_MAX]
    except Exception:
        return []


def recent_roots_save(root, path=None):
    """把 root 记到最近清单头部(去重、上限 10)。返回新清单。"""
    path = path or RECENT_FILE
    roots = [r for r in recent_roots_load(path)
             if os.path.abspath(r) != os.path.abspath(root)]
    roots.insert(0, os.path.abspath(root))
    roots = roots[:RECENT_MAX]
    try:
        import json as _json
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _json.dump(roots, open(path, "w", encoding="utf-8"))
    except Exception:
        pass
    return roots


# ── 树扫描与 Mermaid 投影 ───────────────────────────────────

def scan_tasks(root):
    """全树任务表：任务目录 → 弧行（类级视图）。带 {实例} 记号的任务
    load_task 会拒载（M1 定义无载荷），回退 frontmatter 行——记号原样
    当字符串，同槽同串即同库所，类级图恰好要这个。"""
    out = {}
    for md in glob.glob(os.path.join(root, "**", "方法", "*", "任务.md"),
                        recursive=True):
        tdir = os.path.dirname(md)
        try:
            out[tdir] = eng.load_task(tdir, root)["rows"]
        except SystemExit:
            rows, _ = eng._frontmatter_rows(md)
            kroot = os.path.dirname(os.path.dirname(tdir))   # 类根
            for r in rows:
                rel = (r["pdir"] + "/" if r["pdir"] not in ("", "*") else "")                     + r["pname"]
                # 记号路径按类命名空间化：{实例}/状态.json 五类同串，
                # 直接当库所 id 会把全树焊成一坨（8-11 实测）
                base = kroot if eng.CASE_MARK in rel else root
                r["path"] = os.path.join(base, rel)
                r["desc"] = r.get("desc") or r["pname"]
            out[tdir] = rows
    return out

# ── 实例代数（无实例视角：操作扇出到实例集合）─────────────────

def all_cases(root):
    """实例库全部实例号。单类树（根/方法）:实例/<k> 一级即实例；
    实例库（根/类）:实例/<类>/<k> 二级才是实例，一级是类名不收。"""
    lib = os.path.join(root, "实例")
    if not os.path.isdir(lib):
        return []
    single = os.path.isdir(os.path.join(root, "方法"))
    ks = set()
    for k in os.listdir(lib):
        p = os.path.join(lib, k)
        if not os.path.isdir(p) or k.startswith("."):
            continue
        if single:
            ks.add(k)
            continue
        for k2 in os.listdir(p):
            if os.path.isdir(os.path.join(p, k2)) and not k2.startswith("."):
                ks.add(k2)
    return sorted(ks)


def task_marked(tdir):
    """任务定义是否用 {实例} 记号（M1 模板 → M0 实例代入）。"""
    md = os.path.join(tdir, "任务.md")
    if os.path.isfile(md):
        txt = open(md, encoding="utf-8", errors="replace").read()
    else:
        mds = sorted(glob.glob(os.path.join(tdir, "__*任务定义*.md")))
        if not mds:
            return False
        txt = open(mds[0], encoding="utf-8", errors="replace").read()
    return "{实例}" in txt


def class_cases(root, tdir):
    """实例库中本任务所属类的实例号（货架=类名；单类树货架退化一级）。"""
    kr = eng.klass_rel(tdir, root)
    shelf = os.path.join(root, "实例", os.path.basename(kr)) \
        if kr else os.path.join(root, "实例")
    if not os.path.isdir(shelf):
        return []
    return sorted(k for k in os.listdir(shelf)
                  if os.path.isdir(os.path.join(shelf, k))
                  and not k.startswith("."))


def task_accounts(root, tdir):
    """(实例号, 账目录) 列表——账是 M0：实例模式落 实例/<类>/<k>/__账/，
    单案树落任务目录。以 eng.load_task+rec_dir 权威定位（含根上提校准）。
    返回账**目录**：账文件名归底物（json= __结果.json / xlsx= __账.xlsx），
    读用 eng.load_account(rec_dir, root)，存在性用 eng._account_exists。"""
    out = []
    if task_marked(tdir):
        for c in class_cases(root, tdir):
            try:
                t = eng.load_task(tdir, case=c)
            except SystemExit:
                continue
            out.append((c, eng.rec_dir(t)))
    else:
        try:
            t = eng.load_task(tdir)
        except SystemExit:
            return out
        out.append((None, eng.rec_dir(t)))
    return out


def task_view(root, tdir):
    """带受体的任务视图：{实例}任务取首个可解析实例代入（树徽章/血缘/
    工作流图用），类级任务照旧。逐实例精确判词走 preflight_verdicts。"""
    if not task_marked(tdir):
        try:
            return eng.load_task(tdir)
        except SystemExit:
            return None
    for c in class_cases(root, tdir):
        try:
            return eng.load_task(tdir, case=c)
        except SystemExit:
            continue
    return None


def stale_inputs(root, tdir):
    """任一实例的账报输入已变 ⟳（账是 M0：实例模式在 实例/<类>/<k>/__账/，
    单案树在任务目录——按 eng.rec_dir 权威定位，不再读错地方）。"""
    stale = []
    for _case, rec_dir in task_accounts(root, tdir):
        try:
            rec = eng.load_account(rec_dir, root)
        except (ValueError, OSError):
            continue
        if not rec:
            continue
        for it in rec.get("输入清单", []):
            p = os.path.join(root, it.get("名称", ""))
            if os.path.isfile(p) and "sha256" in it \
                    and eng.sha256(p) != it["sha256"]:
                name = os.path.basename(it["名称"])
                if name not in stale:
                    stale.append(name)
    return stale


def violated_facts(root, tdir, scanned=None):
    """事实件被篡改清单（账标「事实」且 账实 sha 不符）。
    审计红线：这不是过期（重算），是违规（呈人裁决）。
    scanned=外部缓存的 scan_tasks(root) 结果（逐任务循环时传入免重扫）。"""
    bad = []
    for _case, rec_dir in task_accounts(root, tdir):
        try:
            rec = eng.load_account(rec_dir, root)
        except (ValueError, OSError):
            continue
        if not rec:
            continue
        for it in rec.get("输入清单", []):
            if not it.get("事实"):
                continue
            p = os.path.join(root, it.get("名称", ""))
            if os.path.isfile(p) and "sha256" in it \
                    and eng.sha256(p) != it["sha256"]:
                n = os.path.basename(it["名称"])
                if n not in bad:
                    bad.append(n)
    return bad


def status_snapshot(root, tasks, stale_map, lint_counts):
    """老子快照：包根 + 对账计数 + 逐任务（⟳ 态 + 逐实例最近账）。
    lint_counts=(错误数, 警告数)；tasks=任务目录集合；stale_map=tdir→bool。"""

    lines = [f"包根：{os.path.basename(root)}",
             f"对账：{lint_counts[0]} 错 {lint_counts[1]} 警"
             "（10 错为行0规范空白基线）"]
    for tdir in sorted(tasks):
        rel = os.path.relpath(tdir, root)
        stale = "⟳过期" if stale_map.get(tdir) else "新鲜"
        last, nrec = "", 0
        for _case, rec_dir in task_accounts(root, tdir):   # 账是 M0：逐实例
            try:
                d = eng.load_account(rec_dir, root)
            except (ValueError, OSError):
                d = None
            if not d:
                continue
            nrec += 1
            nv = len(d.get("验证动作", []))
            last = (f"；上次点火 {d.get('开始', d.get('回填时间', '?'))} "
                    f"{d.get('状态', '')} 批次 {d.get('批次标识', '-')}"
                    f" 验证动作 {nv} 项")
        if nrec > 1:
            last += f"（{nrec} 实例有账）"
        lines.append(f"任务 {rel}：{stale}{last}")
    return "\n".join(lines)


def triage_lint(errors, warnings):
    """修复提案三桶分诊：(① 规范空白待对表, ② 过期信号, ③ 真悬空可提案)。
    输入是 lint 报告的 errors/warnings 列表——分类规则零 UI 依赖。"""
    import re as _re
    b1, b2, b3 = [], [], []
    for where, msg in list(errors) + list(warnings):
        fpart = where.split("#")[0].split("·")[0]
        if "字节数不符" in msg or "sha256 不符" in msg:
            b2.append((where, msg, fpart))
            continue
        if "机器绝对路径" in msg:
            b1.append((where, msg, "根变量绑定规则待对表"))
            continue
        m = _re.search(r"不存在 '([^']+)'", msg)
        name = m.group(1) if m else ""
        holder = os.path.basename(os.path.dirname(fpart))
        if "近端绑定悬空" in msg and name == holder:
            b1.append((where, msg, "行0 自声明惯例待对表"))
        elif "远端绑定悬空" in msg and name and name in msg.split("::")[0] + msg \
                and name == os.path.basename(
                    msg.split("内不存在")[0].rstrip().split("\\")[-1]):
            b1.append((where, msg, "自指外联行（行0 变体）待对表"))
        else:
            b3.append((where, msg, fpart))
    return b1, b2, b3


def coverage_report(root):
    """MBT 覆盖报告(P3)——引擎单副本,此包装供 explorer 渲染调用。"""
    return eng.coverage_report(root)


def preflight_verdicts(root, tdir):
    """逐受体预检判词：[(实例号, 判词)]，{实例}任务每实例一行；
    类级任务单行。判词含 emoji/HTML 色标（渲染约定归 core，接口零 Qt）。"""
    out = []
    for c, _rp in task_accounts(root, tdir):
        try:
            task = eng.load_task(tdir, case=c)
        except SystemExit as e:
            out.append((c, f"{c or '—'}：<b style='color:#c62828'>{e}</b>"))
            continue
        rows = eng.preflight_rows(task)
        v = "🟢 使能" if rows[-1][4] else "🔴 未使能"
        hint = f"（{rows[-1][3]}）" if rows[-1][3] else ""
        out.append((c, f"{c or '类级'}：{v}{hint}"))
    return out


def one_record_html(root, case, rec_dir):
    """单实例点火记录 → HTML 片段（读账+新鲜度比对，账底物归 store）。"""
    try:
        rec = eng.load_account(rec_dir, root)
    except (ValueError, OSError) as e:
        return f"<p>账解析失败：{e}</p>"
    if not rec:
        return ""
    h = [f"<h4>点火记录（实例 {case}）</h4><p>" if case
         else "<h4>点火记录</h4><p>"]
    for k in ("状态", "批次标识", "IO模式", "引擎", "开始", "结束",
              "回填时间", "备注"):
        if rec.get(k):
            h.append(f"{k}：{rec[k]}<br>")
    h.append("</p>")
    for kind in ("输入清单", "产物清单"):
        items = rec.get(kind, [])
        if not items:
            continue
        rows = []
        for it in items:
            name = it.get("名称", "")
            p = os.path.join(root, name)
            fresh = ("✓" if os.path.isfile(p) and
                     eng.sha256(p) == it.get("sha256") else "✗ 已变")
            cell = (f"<a href='i3dna:{name}'>{name}</a>"
                    if os.path.exists(p) else name)
            rows.append(f"<tr><td>{cell}</td>"
                        f"<td>{it.get('字节','')}</td>"
                        f"<td>{str(it.get('sha256',''))[:12]}…</td>"
                        f"<td>{fresh}</td></tr>")
        h.append(f"<h4>{kind}</h4><table border=1 cellspacing=0 cellpadding=3>"
                 "<tr><th>名称</th><th>字节</th><th>sha256</th><th>新鲜</th></tr>"
                 + "".join(rows) + "</table>")
    if rec.get("缺失输入或产物"):
        h.append("<h4>缺失输入或产物</h4><p>"
                 + "<br>".join(f"{m.get('名称','')}（{m.get('原因','')}）"
                               for m in rec["缺失输入或产物"]) + "</p>")
    return "".join(h)


def _mmid(s, prefix):
    import hashlib
    return prefix + hashlib.md5(s.encode()).hexdigest()[:8]


def 场所拓扑(root):
    """场所视角数据（ARCHITECTURE §1/§5 域与场所正交、N:M 装配）：
    根场所=企业（全类、全实例库）；声明场所=场所/<名>.md 装配多域
    （类集=所列域并集，「全部」=全域）；部门场所=每域一个。
    返回 [(场所名, 是根场所, [类名...], 种, 锚路径)]——种∈根/声明/域，
    锚=声明文件或域目录。零 Qt 无头可测；无域树退化为仅根场所。"""
    t = mdl.树根(os.path.abspath(root))
    return [(s.名, s.是根场所, [c.名 for c in s.类集()], s.种, s.锚路径)
            for s in t.场所们()]


# ── 登录主体（凭证住人员档案；/etc/shadow 同款：盐+慢哈希，无明文） ──

def set_credential(bag, password, iters=240000):
    """把登录凭证写进人员档案（实例/人员/<姓名>/凭证.md）。
    pbkdf2_sha256$<轮数>$<盐hex>$<哈希hex>——树上只放验证子，永不放明文。"""
    import hashlib
    import secrets
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(),
                            salt.encode(), iters)
    p = os.path.join(bag, "凭证.md")
    os.makedirs(bag, exist_ok=True)
    open(p, "w", encoding="utf-8").write(
        f"pbkdf2_sha256${iters}${salt}${h.hex()}\n")
    return p


def verify_credential(bag, password):
    """验证口令：读凭证.md 现算比对（恒时比较）；无凭证=该主体未开通。"""
    import hashlib
    import hmac
    p = os.path.join(bag, "凭证.md")
    if not os.path.isfile(p):
        return False
    t = open(p, encoding="utf-8").read().strip()
    try:
        _, iters, salt, hexh = t.split("$")
        h = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                salt.encode(), int(iters))
        return hmac.compare_digest(h.hex(), hexh)
    except ValueError:
        return False


def find_principal(root, ident):
    """按 员工编号 或 档案名（姓名）找人。返回
    {"编号","姓名","袋","主体值"}；找不到 None。主体值=实例/人员/<袋名>
    ——engine 点火三元组的执行者格式（实例/<类>/<k>）。"""
    库 = os.path.join(root, "实例", "人员")
    if not os.path.isdir(库):
        return None
    for d in sorted(os.listdir(库)):
        bag = os.path.join(库, d)
        if not os.path.isdir(bag) or d.startswith((".", "__")):
            continue
        p = os.path.join(bag, "员工编号.md")
        eid = (open(p, encoding="utf-8").read().strip()
               if os.path.isfile(p) else "")
        if ident in (eid, d):
            return {"编号": eid or d, "姓名": d, "袋": bag,
                    "主体值": f"实例/人员/{d}"}
    return None


def class_roots(root):
    """类根迭代器（v2.1 平铺 类/* 与 v2.2 域聚簇 域/*/类/* 统一产出）。
    结构判据：含 方法/ 子目录才是类根。老树新树同形对待。"""
    seen = set()
    pats = (glob.glob(os.path.join(root, "类", "*")),
            glob.glob(os.path.join(root, "域", "*", "类", "*")))
    for croot in sorted(p for p in pats for p in p):
        if croot in seen:
            continue
        seen.add(croot)
        if os.path.isdir(os.path.join(croot, "方法")):
            yield croot


def _pkg_of(root, tdir):
    """任务的包名（mermaid 按类过滤的键）：类根 basename——
    v2.2 域聚簇下 域/X/类/Y/方法/T 的包名是 Y 不是 X（域≠类）。"""
    parts = os.path.relpath(tdir, root).split(os.sep)
    if "类" in parts:
        i = parts.index("类")
        if len(parts) > i + 1:
            return parts[i + 1]
    return parts[0]


def mermaid_text(root, pkg="全部"):
    """执行流 → Mermaid flowchart（第五投影面：同一份弧声明的又一次渲染）。
    Obsidian/GitHub 原生渲染，零绘图代码。"""
    allrows = {t: r for t, r in scan_tasks(root).items()
               if pkg == "全部" or _pkg_of(root, t) == pkg}
    rows_f, arcs, places, opt_inputs = gather_arcs(
        root, allrows, False, "全部")
    lines = ["flowchart LR",
             "  classDef red fill:#c62828,color:#fff,stroke:#8e0000",
             "  classDef green fill:#388e3c,color:#fff,stroke:#1b5e20",
             "  classDef blue fill:#1565c0,color:#fff,stroke:#0d47a1",
             "  classDef place fill:#e8f5e9,color:#1b5e20,stroke:#9e9e9e"]
    kindcls = {"红": "red", "绿": "green", "蓝": "blue"}
    seen_p = set()
    for ci, cnodes in enumerate(components(rows_f, arcs, root)):
        ctasks = [n for n in cnodes if n in rows_f]
        if not ctasks:
            continue
        cap = _pkg_of(root, ctasks[0])
        lines.append(f"  subgraph C{ci}[{cap}]")
        for t in sorted(ctasks):
            k = task_kind(t)
            mark = {"红": "🔴", "绿": "🟢", "蓝": "🔵"}[k]
            lines.append(f"    {_mmid(t, 'T')}[\"{mark} {os.path.basename(t)}\"]"
                         f":::{kindcls[k]}")
        for p in sorted(n for n in cnodes if n in places and n not in seen_p):
            seen_p.add(p)
            lines.append(f"    {_mmid(p, 'P')}((\"{places[p][:14]}\")):::place")
        lines.append("  end")
    for t, p, k in arcs:
        dash = "-.->" if (k == "输入" and (t, p) in opt_inputs) else "-->"
        a, b = (_mmid(p, "P"), _mmid(t, "T")) if k == "输入"             else (_mmid(t, "T"), _mmid(p, "P"))
        lines.append(f"  {a} {dash} {b}")
    return "\n".join(lines) + "\n"


import re as _re
_CASE_CLASS_RE = _re.compile(r"^实例/([^/]+)/")

def slot_coverage(root, edit_path):
    """编辑器办单助手的机械层：文件路径 → 消费它的方法 → 目标类 schema 键清单。

    输入弧反查（谁吃这个文件）→ 该方法产物弧的目标类（实例/<类>/…）
    → 类根/schema.md 键说明区的键名序列。纯声明推导,零 LLM——
    LLM 只在「申请文本已给哪些键」的抽取层用（同输入同输出的确定性管道）。"""
    import yaml
    rel = os.path.relpath(edit_path, root)
    parts = rel.split(os.sep)
    # 1) 反查消费方法：本文件是某任务输入弧的 case 代入物
    #    （弧 path 为 实例/<类>/<X>/<名>，编辑文件为 实例/<类>/<case>/<名>，X 对位任意 case）
    consumers = []
    for tdir, _kind in scan_tasks(root).items():
        try:
            t = eng.load_task(tdir, root, case="X")
        except SystemExit:
            continue
        for r in t.get("rows", []):
            if r.get("kind") != "输入" or not r.get("path"):
                continue
            ap = os.path.relpath(r["path"], root).split(os.sep)
            if len(ap) == len(parts) and ap[:2] == parts[:2] \
                    and len(ap) > 3 and ap[2] == "X" and ap[3:] == parts[3:]:
                consumers.append((tdir, r))
                break
            if ap == parts:                    # 无记号弧字面命中
                consumers.append((tdir, r))
                break
    if not consumers:
        return None
    tdir, inarc = consumers[0]
    # 2) 该方法产物弧的目标类（实例/<类名>/… 的 <类名>）
    t = eng.load_task(tdir, root, case="X")
    targets = []
    for r in t.get("rows", []):
        if r.get("kind") != "产物" or not r.get("path"):
            continue
        rp = os.path.relpath(str(r["path"]), root)   # path 可能是绝对路径
        m = _CASE_CLASS_RE.match(rp)
        if m and m.group(1) not in targets:
            targets.append(m.group(1))
    if not targets:
        return {"task": tdir, "input": inarc, "schema_keys": None}
    # 3) 目标类 schema.md 键说明区的键名
    kname = targets[0]
    croot = _find_croot(root, kname)
    keys, defaults = None, {}
    if croot:
        sp = os.path.join(croot, "schema.md")
        if os.path.isfile(sp):
            fm = open(sp, encoding="utf-8").read().split("---")
            decl = yaml.safe_load(fm[1]) if len(fm) > 2 else {}
            keys = list((decl.get("键说明") or {}).keys())
            defaults = decl.get("默认") or {}
    return {"task": tdir, "input": inarc.get("desc") or inarc.get("pname"),
            "target_class": kname, "schema_keys": keys, "defaults": defaults}


def _find_croot(root, kname):
    """类名→类根（含纯 schema 实体类——class_roots 只产出过程类）。"""
    for c in (os.path.join(root, "类", kname),
              *glob.glob(os.path.join(root, "域", "*", "类", kname))):
        if os.path.isdir(c):
            return c
    return None
def green_work_for(root, edit_path):
    """实例文件 → 消费它的绿任务（执行者:人）+ case。
    架构裁决:通用界面（聊天收参+编辑器+唯一确认按钮）是人类和系统
    交互的通用通道——双击待办单据开通用界面办理,不落裸编辑器。
    ①路径是 实例/<类>/<case>/… ②某任务输入弧 case 代入命中
    ③该任务是绿（执行者:人）。返回 (tdir, case) 或 None。"""
    rel = os.path.relpath(edit_path, root)
    if not _CASE_CLASS_RE.match(rel):
        return None
    parts = rel.split(os.sep)
    for tdir, _kind in scan_tasks(root).items():
        try:
            t = eng.load_task(tdir, root, case="X")
        except SystemExit:
            continue
        for r in t.get("rows", []):
            if r.get("kind") != "输入" or not r.get("path"):
                continue
            ap = os.path.relpath(r["path"], root).split(os.sep)
            if len(ap) == len(parts) and ap[:2] == parts[:2] \
                    and ap[2] == "X" and ap[3:] == parts[3:]:
                if task_kind(tdir) == "绿":
                    return tdir, parts[2]
                break        # 此任务非绿——看下一个任务的弧
    return None


def instance_stations(root, croot, case):
    """实例工位面板的机械层：本 case 的逐站状态清单。
    调用约定统一论(99号):一切点火都是实例侧调用——
    有状态 bean(实例方法,弧含{实例})以 case 代入;无状态 bean(类方法,
    弧无记号)按产物弧路径是否落在 实例/<类>/<case>/ 下归属(早绑定)。
    每站: {task, kind, human, need, reason}。kind 见 task_kind,
    need/reason 直译引擎 _task_needs_fire。"""
    out = []
    for t in class_methods(croot):
        name = os.path.basename(t)
        md = os.path.join(t, "任务.md")
        body = open(md, encoding="utf-8", errors="replace").read()
        # {案卷号} 弧也是 case 绑定(有状态 bean):显式跨架路径代入需 case
        has_mark = (eng.CASE_MARK in body or eng.CASE_NUM_MARK in body)
        if not has_mark:
            # 无状态 bean(类方法):归属=产物弧路径 实例/<实体>/<case>/ 前缀
            # 命中本 case 名(实体库与过程类库异名,不能按 croot 名推目录)
            try:
                task = eng.load_task(t, root, case=None)
            except SystemExit:
                continue
            hit = False
            for r in task.get("rows", []):
                if r.get("kind") != "产物" or not r.get("path"):
                    continue
                rp = os.path.relpath(str(r["path"]), root)
                seg = rp.split(os.sep)
                if len(seg) > 3 and seg[0] == "实例" and seg[2] == case:
                    hit = True
                    break
            if not hit:
                continue
            tcase = None                     # 类方法点火不带 case
        else:
            tcase = case
        try:
            need, reason = eng._task_needs_fire(t, root, tcase)
        except SystemExit as e:
            need, reason = False, str(e)
        out.append({"task": t, "name": name, "kind": task_kind(t),
                    "human": eng.get_value(os.path.join(t, "任务.md"),
                                           "执行者") == "人",
                    "need": need, "reason": reason, "case": tcase})
    return out


API_READ_VERBS = ("tree", "tasks", "task", "account", "lint", "coverage")


def api_query(root, verb, args=(), timeout=20):
    """老子手艺·读桥查询（8-19）：白名单只开读动词——老师傅（爱因斯坦）
    可以盘问一切，写桥（点火/办结）归人（泰勒的工位不动摇）。返回
    (ok, text)；拒绝也机读回喂，模型照拒词改问法。"""
    import subprocess as _sp
    import sys as _sys
    if verb not in API_READ_VERBS:
        return False, ("【拒】" + str(verb) + " 不在读桥白名单（"
                       + "、".join(API_READ_VERBS)
                       + "）——写桥归人：点火/办结走工位按钮")
    cmd = [_sys.executable,
           os.path.join(BASE, "i3dna-engine", "i3dna_api.py"),
           verb, os.path.abspath(root)] + [str(a) for a in args][:6]
    try:
        r = _sp.run(cmd, capture_output=True, text=True, timeout=timeout)
    except _sp.TimeoutExpired:
        return False, f"【拒】{verb} 超时（{timeout}s）"
    out = (r.stdout or "").strip()
    if not out:
        return False, ((r.stderr or "").strip() or "（空输出）")[:400]
    return True, out[:6000] + ("\n…（截断，改窄查询：--task/--case）"
                              if len(out) > 6000 else "")


API_WRITE_VERBS = ("fire", "settle", "advance", "draft")


def api_write(root, verb, args=(), timeout=600, stdin_text=None):
    """右键对话·写桥签字（101号）＋起草（103号）：fire/settle/advance
    签变迁、draft 柜员的手（草稿落案卷零入账，stdin JSON 载荷）——
    均经 i3dna_api.py 写桥直通引擎（引擎仍是唯一写路径）；返回
    (ok, text)。login 不在对话签字面——签字=授权变迁，登录是身份
    不是变迁。"""
    import subprocess as _sp
    import sys as _sys
    if verb not in API_WRITE_VERBS:
        return False, ("【拒】" + str(verb) + " 不在签字面（"
                       + "、".join(API_WRITE_VERBS)
                       + "）——对话只签变迁（fire/settle/advance）"
                         "与起草（draft）")
    cmd = [_sys.executable,
           os.path.join(BASE, "i3dna-engine", "i3dna_api.py"),
           verb, os.path.abspath(root)] + [str(a) for a in args]
    # 进程组起跑＋超时击杀全组（含 api.py 的引擎孙进程）——只杀直接子进程
    # 会留孤儿引擎迟到写账，与「拒=零副作用」的回显语义打架（101号验收）。
    import os as _os
    import signal as _sig
    proc = _sp.Popen(cmd, stdout=_sp.PIPE, stderr=_sp.PIPE, text=True,
                     stdin=_sp.PIPE if stdin_text is not None else None,
                     start_new_session=True)
    try:
        out, err = proc.communicate(input=stdin_text, timeout=timeout)
    except _sp.TimeoutExpired:
        try:
            _os.killpg(_os.getpgid(proc.pid), _sig.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        out, err = proc.communicate()
        return False, (f"【拒】{verb} 超时（{timeout}s）——进程组已击杀"
                       "（含引擎孙进程，防迟到入账）")
    text = "\n".join(x for x in ((out or "").strip(), (err or "").strip()) if x)
    return proc.returncode == 0, \
        (text or f"（退出码 {proc.returncode}，无输出）")[:6000]


def assist_llm(prompt, on_delta=None, timeout=60):
    """办单助手直连（deepseek-v4-flash,thinking low）——不走 omp 子进程:
    逐轮交互场景,omp 起进程 6s+默认大模型 24s 不可接受。
    on_delta(text) 有则流式回调(首字~2-4s),无则整段返回。
    key: Keychain deepseek-api-key（与 ~/start-claude-deepseek.sh 同源）。
    实测:DeepSeek 端点不把 budget_tokens 当硬顶——thinking 可吃光全部
    max_tokens 导致 text 零字节(stop_reason=max_tokens,即「助手沉默」)。
    防线（8-19 修订）:基础 16000（端点上限 128K,思考吃不死）;仍空且
    截断 → 关思考重试一次(流式场景零 delta 已发,重试不重复渲染)。"""
    import subprocess as _sp
    import json as _json
    key = _sp.run(["security", "find-generic-password", "-a",
                   os.environ.get("USER", "guci"), "-s", "deepseek-api-key", "-w"],
                  capture_output=True, text=True).stdout.strip()
    if not key:
        raise RuntimeError("Keychain 无 deepseek-api-key")

    def _call(max_tokens, thinking="enabled"):
        payload = {"model": "deepseek-v4-flash", "max_tokens": max_tokens,
                   "thinking": {"type": thinking},
                   "messages": [{"role": "user", "content": prompt}],
                   "stream": on_delta is not None}
        req = urllib.request.Request(
            "https://api.deepseek.com/anthropic/v1/messages",
            data=_json.dumps(payload).encode(),
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        if on_delta is None:
            r = _json.load(resp)
            text = "".join(c.get("text", "") for c in r.get("content", [])
                           if c.get("type") == "text")
            return text, r.get("stop_reason")
        buf, stop = [], None
        for line in resp:                # 流式:同步生成器,首字早到
            if not line.startswith(b"data: "):
                continue
            try:
                ev = _json.loads(line[6:])
            except Exception:
                continue
            d = ev.get("delta", {})
            if ev.get("type") == "content_block_delta" \
                    and d.get("type") == "text_delta":
                buf.append(d["text"])
                on_delta(d["text"])
            elif ev.get("type") == "message_delta":
                stop = ev.get("delta", {}).get("stop_reason", stop)
        return "".join(buf), stop

    text, stop = _call(16000)
    if not text.strip() and stop == "max_tokens":
        # 病态沉思兜底：直接**关思考**重试（思考关了吃不掉预算，正文
        # 必然有字节——收参起草用不上深思）。旧梯子 2400→4800 加倍
        # 仍被思考吃光是 8-19 复发教训；端点上限 128K，基础给足。
        text, stop = _call(8000, thinking="disabled")
    return text


def find_type_file(root, tdir, slot_name):
    """输入槽 → 类型文件（诱导知识件）。两条链，先显式后家族：
    1) 弧声明的「类型:」值 T → 类根/T.md → 根/T.md（trade-v4 dict 弧风格）
    2) 引擎 _type_file 同款家族链：类根/状态/<槽名去扩展>.md → 根/状态/…
       → 类根/消息/… → 根/消息/…（纯路径弧也有知识住址——
       状态/<槽>.md 是档案说明,消息/<槽>.md 是流转件说明）。
    类型文件 = 树上的诱导知识（问序/澄清单模板）,领域自治,
    agent 读它优先于自身常识。"""
    import yaml as _y
    import os as _os
    tname = None
    md = _os.path.join(tdir, "任务.md")
    if _os.path.isfile(md):
        parts = open(md, encoding="utf-8").read().split("---")
        if len(parts) > 2:
            decl = _y.safe_load(parts[1]) or {}
            for arc in decl.get("输入") or []:
                if not isinstance(arc, dict):   # 纯路径弧（无显式类型）走家族链
                    continue
                if arc.get("路径", "").endswith(slot_name):
                    tname = arc.get("类型")
                    break
    kr = _os.path.relpath(_os.path.dirname(_os.path.dirname(tdir)), root)
    kparts = kr.split("/") if kr and kr != "." else []
    cands = []
    if tname:                                  # 链1:显式声明类型
        cands += [_os.path.join(root, *kparts, tname + ".md"),
                  _os.path.join(root, tname + ".md")]
    base = _os.path.splitext(slot_name)[0] + ".md"
    for fam in ("状态", "消息"):                # 链2:引擎家族链
        cands += [_os.path.join(root, *kparts, fam, base),
                  _os.path.join(root, fam, base)]
    for c in cands:
        if _os.path.isfile(c):
            return c
    return None

# ── 机读 CLI（Obsidian 插件等外皮的取数口）─────────────────

def _cli():
    import argparse

    import sys as _s
    import json as _j
    ap = argparse.ArgumentParser(description="i3dna_core 机读接口")
    ap.add_argument("cmd", choices=["overview", "pending", "cases", "kind",
                                    "workform", "instantiate", "mermaid",
                                    "mermaid_files"])
    ap.add_argument("root")
    ap.add_argument("arg1", nargs="?")          # croot / tdir / pkg

    a = ap.parse_args()
    root = os.path.abspath(a.root)

    def out(obj):
        print(_j.dumps(obj, ensure_ascii=False, indent=1))

    if a.cmd == "overview":
        classes = []
        for croot in class_roots(root):
            if not os.path.isdir(os.path.join(croot, "方法")):
                continue
            shelf = os.path.join(root, "实例", os.path.basename(croot))
            classes.append({
                "类": os.path.basename(croot),
                "croot": os.path.relpath(croot, root),
                "方法": [{"名": os.path.basename(t), "色": task_kind(t),
                          "tdir": os.path.relpath(t, root)}
                         for t in class_methods(croot)],
                "构造参数": ctor_params(root, croot),
                "实例": sorted(os.path.basename(d) for d in
                               glob.glob(os.path.join(shelf, "*"))
                               if os.path.isdir(d)
                               and not os.path.basename(d).startswith(
                                   (".", "__")))})
        out({"classes": classes})
    elif a.cmd == "pending":
        out({"待人办": [{"tdir": os.path.relpath(t, root), "由": r}
                        for t, r in pending_human(
                            root, os.path.join(root, a.arg1), a.arg2)]})
    elif a.cmd == "cases":
        out({"实例": task_pending_cases(root, os.path.join(root, a.arg1))})
    elif a.cmd == "kind":
        out({"色": task_kind(os.path.join(root, a.arg1))})
    elif a.cmd == "workform":
        tdir = os.path.join(root, a.arg1)
        try:
            task = eng.load_task(tdir, root, case=a.arg2)
        except SystemExit as e:
            out({"错误": str(e)})
            _s.exit(1)
        rows = []
        for r in task["rows"]:
            if not r["path"]:
                continue
            rows.append({
                "向": r["kind"], "名": r["pname"],
                "rel": os.path.relpath(r["path"], root),
                "可缺": bool(r.get("optional")),
                "消息": eng.is_message(task, r),
                "在场": os.path.isfile(r["path"]),
                "存根": workform_stub(task, r) if r["kind"] == "产物" else ""})
        out({"任务": os.path.basename(tdir), "实例": a.arg2,
             "执行者": task.get("executor") or "",
             "指令": task.get("instruction") or "", "弧": rows})
    elif a.cmd == "instantiate":
        croot = os.path.join(root, a.arg1)
        cdir = case_dir(root, croot, a.arg2)
        if os.path.isdir(cdir):
            out({"错误": f"实例 {a.arg2} 已存在"})
            _s.exit(1)
        os.makedirs(cdir)
        eng.seed_state_defaults(root, croot, cdir)
        slots = ctor_params(root, croot)
        for rel in slots:
            fp = os.path.join(cdir, rel)
            if os.path.dirname(rel):
                os.makedirs(os.path.dirname(fp), exist_ok=True)
            if not os.path.isfile(fp):
                open(fp, "w", encoding="utf-8").close()
        out({"实例": a.arg2, "目录": os.path.relpath(cdir, root),
             "待写构造参数": slots})
    elif a.cmd == "mermaid_files":
        # 一类一图,住类目录——图是类的自我描述,不是树的中央海报
        written = []
        for croot in class_roots(root):
            if not os.path.isdir(os.path.join(croot, "方法")):
                continue
            pkg = os.path.basename(croot)
            txt = (f"# 执行流·{pkg}（机器生成，勿手改——弧声明的投影）\n\n"
                   "```mermaid\n" + mermaid_text(root, pkg) + "```\n")
            fp = os.path.join(croot, "__执行流.md")
            with open(fp, "w", encoding="utf-8") as f:
                f.write(txt)
            written.append(os.path.relpath(fp, root))
        out({"written": written})
    elif a.cmd == "mermaid":
        print("```mermaid\n" + mermaid_text(root, a.arg1 or "全部")
              + "```\n")


if __name__ == "__main__":
    _cli()
