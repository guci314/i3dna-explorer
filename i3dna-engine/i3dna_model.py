# -*- coding: utf-8 -*-
"""i3dna_model —— 目录树逻辑模型的显式实现（九概念 · 两网 · 两边界）。

对应 docs/逻辑模型总图.md（95 号）。设计律：
1. **class 是树的视图,不是数据的副本**——对象锚定树上路径、懒读声明文件,
   内存不存第二份事实源(树是唯一权威;对象是读写视图)。
2. 九概念按网归属:正交{树,身份,边界} + 图网{类,实例(档案),边} +
   Petri网{方法,弧,实例(案卷),账}。
3. 线的两分原则(95 附录):弧与边共享 线 管道基类(实现层),概念分立(语义层)。
   弧管流动(输入/产物两子类),边管相关(继承|关联|聚合|组合 四型枚举,不配层次)。
4. 剃刀已裁:投影并入产物弧(落点:文件|键值区|字段区),部门并入档案,
   案卷库并入树根(导航方法),范畴删除(由目录结构判定:有 方法/=过程类,
   无方法+有 schema.md=实体类)。
5. 中文类名=树的声明语言;本层零 Qt、零 LLM,无头可直测。

用法:
    from i3dna_model import 树根
    t = 树根("trade-v4")
    域s = t.域们()                        # [域, ...]
    产品 = t.找类("产品")                 # 实体类
    上市 = t.找类("产品管理").方法们()[0]  # 方法
    弧 = 上市.输入弧们()                  # [输入弧, ...]
    边们 = 产品.关系们()                  # [边, ...]
    档 = t.档案("产品", "P005")           # 档案(案卷库已并入树根)
"""
import os
import importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))
_BASE = os.path.dirname(_HERE)


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_BASE, rel))
    assert spec is not None and spec.loader is not None, f"装载失败: {rel}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_kv = _load("i3dna_kv", os.path.join("i3dna-engine", "i3dna_kv.py"))


def _fm(path):
    """读声明头,兼容两形:
    标准frontmatter(--- 开头) → yaml 段;
    kv风格(域.md/类.md: 键: 值 行直起, --- 结尾) → 头部 k: v 行逐个解析。"""
    import yaml
    try:
        src = open(path, encoding="utf-8").read()
        parts = src.split("---")
        if len(parts) >= 3 and not parts[0].strip():
            return yaml.safe_load(parts[1]) or {}
        # kv 形:从头逐行收 k: v,遇非声明行/--- 止
        out = {}
        for ln in (parts[0] if parts else src).splitlines():
            s = ln.strip()
            if not s:
                continue
            if ":" not in s:
                break
            k, _, v = s.partition(":")
            out[k.strip()] = v.strip() or None
        return out
    except Exception:
        return {}


def _root_of(path):
    """路径→树根推导(唯一实现,禁止各构造器自己数 dirname):
    从 path 的祖先序列里定位结构分界——'域' 或 '实例' 或 '类' 或 '方法'
    的**父级**即树根。找不到分界(路径根本不在树内)→ raise,不静默给错根。"""
    parts = os.path.abspath(path).split(os.sep)
    for i, p in enumerate(parts):
        if p in ("域", "实例") and i > 0:
            return 树根(os.sep.join(parts[:i]))
        if p == "类" and i > 0:
            return 树根(os.sep.join(parts[:i]))
        if p == "方法" and i > 0:            # 单类树退化: 根/方法/…
            return 树根(os.sep.join(parts[:i]))
    raise ValueError(f"路径不在企业树内(无 域/实例/类/方法 分界): {path}")
# ══════════════ 正交层 ══════════════

class 节点:
    """树上路径锚定基类:一切对象的物理身份是路径。"""
    def __init__(self, path):
        self.path = os.path.abspath(path)

    @property
    def 名(self):
        return os.path.basename(self.path)

    def __repr__(self):
        return f"<{type(self).__name__} {self.名}>"


class 树根(节点):
    """企业树=唯一权威(概念·树)。两网 + 边界都住在这棵树上。"""
    @property
    def 根场所(self):
        """根场所=企业本身(bounded context 树的根)。"""
        return 场所(self.path, root=self)

    def 场所们(self):
        """场所拓扑:根场所 + 声明场所(场所/<名>.md 装配清单,N:M——一场所
        装配多域,类集=所列域并集;Spring 一个 context scan 多 package 的
        同构物) + 未被认领域的部门场所(引导态 1:1;已认领域由声明场所
        接管——费米律,一实例恰属一场所,8-19 审计落定)。
        域静态管类,场所运行时管实例;部门场所的实例集=域内类的实例架。"""
        out = [self.根场所]
        认领 = set()
        场所根 = os.path.join(self.path, "场所")
        if os.path.isdir(场所根):
            for f in sorted(os.listdir(场所根)):
                if not f.endswith(".md"):
                    continue
                fm = _fm(os.path.join(场所根, f)) or {}
                装配 = fm.get("装配") or []
                if 装配:
                    out.append(场所(os.path.join(场所根, f), root=self,
                                    装配=[str(x) for x in 装配]))
                    认领 |= {str(x) for x in 装配}
        if "全部" not in 认领:
            out += [场所(d.path, root=self, 域对象=d)
                    for d in self.域们() if d.名 not in 认领]
        return out

    def 域们(self):
        out = []
        d = os.path.join(self.path, "域")
        if os.path.isdir(d):
            out = [域(os.path.join(d, x)) for x in sorted(os.listdir(d))
                   if os.path.isdir(os.path.join(d, x))]
        return out
    def _类路径们(self):
        """全部类根路径(内部用,字符串)。两形:根/类/* 与 根/域/*/类/*。"""
        out = []
        old = os.path.join(self.path, "类")
        if os.path.isdir(old):
            out += [os.path.join(old, x) for x in sorted(os.listdir(old))]
        for dom in self.域们():
            out += dom._类路径们()
        return [c for c in out if os.path.isdir(c)]

    def _是类根(self, croot):
        """分类器(唯一,_造类 与过滤共用):有 方法/=过程类;类.md 范畴=实体
        或(无方法 + 有 schema.md)=实体类。口径一致,杜绝"滤掉但造得出"。"""
        if os.path.isdir(os.path.join(croot, "方法")):
            return True
        p = os.path.join(croot, "类.md")
        if os.path.isfile(p) and _fm(p).get("范畴") == "实体":
            return True
        return os.path.isfile(os.path.join(croot, "schema.md"))

    def 类们(self):
        """全部类对象(实体类+过程类)。与 域.类们() 同返回类型。"""
        return [self._造类(c) for c in self._类路径们()
                if self._是类根(c)]

    def 找类(self, 名):
        """类名→类对象(实体类或过程类;找不到 None)。"""
        for c in self.类们():
            if c.名 == 名:
                return c
        return None

    def _造类(self, croot):
        if self._是类根(croot) and not os.path.isdir(os.path.join(croot, "方法")):
            return 实体类(croot, self)     # 无方法+有范畴/schema=实体
        if not self._是类根(croot):
            return None                    # 非类根不造(调用方已过滤,防御)
        return 过程类(croot, self)

    # ── 实例层导航(案卷库已并入树根,剃刀裁决) ──
    def _实例(self):
        return os.path.join(self.path, "实例")

    def 架们(self):
        """实例/<类>/<k> 的类架清单(Bean 平铺,不按域搬)。"""
        if not os.path.isdir(self._实例()):
            return []
        return [x for x in sorted(os.listdir(self._实例()))
                if os.path.isdir(os.path.join(self._实例(), x))]

    def 全案卷号(self):
        """全部实例号集合(跨架全集)。单类树退化形: 根/方法/… 时实例平铺。"""
        out = set()
        单类 = os.path.isdir(os.path.join(self.path, "方法"))
        for k in self.架们() if not 单类 else []:
            for x in os.listdir(os.path.join(self._实例(), k)):
                if not x.startswith((".", "__")) and os.path.isdir(
                        os.path.join(self._实例(), k, x)):
                    out.add(x)
        if 单类:
            out = {x for x in os.listdir(self._实例())
                   if not x.startswith((".", "__"))
                   and os.path.isdir(os.path.join(self._实例(), x))}
        return out

    def 档案(self, 类名, 实体号):
        return 档案(os.path.join(self._实例(), 类名, 实体号), self)

    def 档案们(self, 类名):
        d = os.path.join(self._实例(), 类名)
        if not os.path.isdir(d):
            return []
        return [档案(os.path.join(d, x), self)
                for x in sorted(os.listdir(d))
                if os.path.isdir(os.path.join(d, x))
                and not x.startswith((".", "__"))]

    def 案卷(self, 类名, 案卷号):
        return 案卷(os.path.join(self._实例(), 类名, 案卷号), self)

    def 部门们(self):
        """部门=实体类「部门」的档案(部门类已并入档案,剃刀裁决)。"""
        d = os.path.join(self._实例(), "部门")
        return [档案(os.path.join(d, x), self)
                for x in sorted(os.listdir(d))
                if os.path.isdir(os.path.join(d, x))
                and not x.startswith((".", "__"))] if os.path.isdir(d) else []


class 域(节点):
    """域=Java package(概念·边界·静态面)。管理类的集合(M1 定义聚簇):
    实体类/过程类/消息类型住域下。归纳就是修改域的类——域保证生殖隔离
    (修正案不跨域杂交);跨域只走显式接口(共享库所/消息)。
    一致性归 case(93 号: 域管类聚簇,case 管事务)。"""
    def __init__(self, path):
        super().__init__(path)
        self.声明 = _fm(os.path.join(path, "域.md"))             if os.path.isfile(os.path.join(path, "域.md")) else {}

    @property
    def 域主(self):
        return self.声明.get("域主")

    @property
    def 职责(self):
        return self.声明.get("职责")

    @property
    def 白名单(self):
        v = self.声明.get("跨域白名单")
        if isinstance(v, str) and v.startswith("[") and v.endswith("]"):
            return [x.strip() for x in v[1:-1].split(",") if x.strip()]
        return v

    def _类路径们(self):
        c = os.path.join(self.path, "类")
        if not os.path.isdir(c):
            return []
        return [os.path.join(c, x) for x in sorted(os.listdir(c))
                if os.path.isdir(os.path.join(c, x))]

    def 类们(self):
        根 = _root_of(self.path)
        return [根._造类(p) for p in self._类路径们() if 根._是类根(p)]


class 场所(节点):
    """场所=bounded context(概念·场所·运行时层,ARCHITECTURE.md §1/§5)。
    组织实例(案卷/档案/bean 装配)——与域正交:域静态管类,场所运行时管实例。
    三重语义的机械面:①整合(场内激活的类集+实例集);②记忆锚(工作目录→
    场所→项目记忆);③语言边界(词表=场内类集的键并集,演绎场内自洽)。
    拓扑:树根=根场所(企业=整个实例库);声明场所=装配多域(N:M,清单住
    场所/<名>.md);域=部门场所(场内实例=域内各类的实例架并集);
    无域单类树退化为根场所即全部。"""
    def __init__(self, path, root=None, 域对象=None, 装配=None):
        super().__init__(path)
        self.根 = root or _root_of(path)
        self.域 = 域对象          # None=非部门场所;否则=本场所对应的域(部门)
        self.装配 = [str(x) for x in (装配 or [])]   # 声明场所:装配域名清单

    @property
    def 名(self):
        n = super().名
        return n[:-3] if self.装配 and n.endswith(".md") else n

    @property
    def 种(self):
        return "根" if self.是根场所 else ("声明" if self.装配 else "域")

    @property
    def 是根场所(self):
        return self.域 is None and not self.装配

    @property
    def 锚路径(self):
        """记忆锚:激活此场所记忆的目录路径(invoke_memory 语义)。"""
        return self.path

    def 类集(self):
        """整合:场内激活的类——根场所=全类;声明场所=装配清单各域类集
        的并集(「全部」=所有域);部门场所=域.类们()。"""
        if self.是根场所:
            return list(self.根.类们())
        if self.装配:
            out = []
            for d in self.根.域们():
                if "全部" in self.装配 or d.名 in self.装配:
                    out += d.类们()
            return out
        return self.域.类们()

    def 实例们(self):
        """场内实例(案卷+档案)——根场所=全实例库;部门场所=域内
        各类的实例架并集(实例/<类>/<k>)。"""
        库 = os.path.join(self.根.path, "实例")
        if not os.path.isdir(库):
            return []
        架集 = ({c.名 for c in self.类集()} if not self.是根场所
                else set(self.根.架们()))
        out = []
        for 架 in sorted(架集):
            p = os.path.join(库, 架)
            if not os.path.isdir(p):
                continue
            out += [os.path.join(p, x) for x in sorted(os.listdir(p))
                    if os.path.isdir(os.path.join(p, x))
                    and not x.startswith((".", "__"))]
        return out

    def 词表(self):
        """语言边界(演绎侧):场内词=场内类集的 schema 键并集。"""
        词 = set()
        for c in self.类集():
            sch = getattr(c, "声明", {}) or {}
            词 |= set((sch.get("键说明") or {}).keys())
        return 词

# ══════════════ 图数据库网(静) ══════════════

class 类(节点):
    """类基(概念·类):类.md 声明的公共读取。范畴字段已剃(目录结构判定)。"""
    def __init__(self, path, root=None):
        super().__init__(path)
        self.根 = root or _root_of(path)
        self.声明 = _fm(os.path.join(path, "类.md"))             if os.path.isfile(os.path.join(path, "类.md")) else {}

    def 关系们(self):
        """关系声明 → 边对象(概念·边,图网的线)。与 方法们()/类们() 同惯例:
        构造对象=方法,读属性=property。"""
        return [边(r, self) for r in (self.声明.get("关系") or [])
                if isinstance(r, dict)]


class 实体类(类):
    """实体类(continuant):主数据的类型。schema.md=键说明/属主/默认。"""
    @property
    def schema声明(self):
        return _fm(os.path.join(self.path, "schema.md"))             if os.path.isfile(os.path.join(self.path, "schema.md")) else {}

    @property
    def 键说明(self):
        return self.schema声明.get("键说明") or {}

    @property
    def 属主表(self):
        return self.schema声明.get("属主") or {}

    @property
    def 默认表(self):
        return self.schema声明.get("默认") or {}

    def 档案们(self):
        return self.根.档案们(self.名)


class 过程类(类):
    """过程类(occurrent):无持久状态,方法/至少一个。"""
    def 方法规(self):
        m = os.path.join(self.path, "方法")
        if not os.path.isdir(m):
            return []
        return [os.path.join(m, x) for x in sorted(os.listdir(m))
                if os.path.isdir(os.path.join(m, x))
                and os.path.isfile(os.path.join(m, x, "任务.md"))]

    def 方法们(self):
        return [方法(p, self.根) for p in self.方法规()]
# ══════════════ Petri 网(动) ══════════════

class 方法(节点):
    """方法=SOP=Petri 变迁(概念·方法)。任务.md=弧声明+指令。"""
    def __init__(self, path, root=None):
        super().__init__(path)
        self.根 = root or _root_of(path)
        self.声明 = _fm(os.path.join(path, "任务.md"))

    @property
    def 指令(self):
        # 声明头只剥第一对 ---,正文里的水平线不是分界(前两段重组后保留原样)
        src = open(os.path.join(self.path, "任务.md"),
                   encoding="utf-8").read()
        import re as _re
        m = _re.match(r"^---[ \t]*\n.*?\n---[ \t]*(?:\n|$)", src, _re.S)
        return src[m.end():].strip() if m else src.strip()

    @property
    def 执行者声明(self):
        return self.声明.get("执行者")

    @property
    def 色(self):
        """红=符号程序在场,绿=执行者:人,蓝=其余(agent)。"""
        if os.path.isdir(os.path.join(self.path, "执行程序")):
            return "红"
        if self.执行者声明 == "人":
            return "绿"
        return "蓝"

    def 弧们(self, 段名):
        out = []
        for r in self.声明.get(段名) or []:
            if 段名 == "输入":
                out.append(输入弧(r, self))
            elif 段名 in ("产物", "投影"):
                out.append(产物弧(r, self))
        return out

    def 输入弧们(self):
        return self.弧们("输入")

    def 产物弧们(self):
        """产物弧们=产物段+投影段(投影已并入产物弧,剃刀裁决)。"""
        return self.弧们("产物") + self.弧们("投影")


class 线:
    """线基(管道,非概念):声明行+源。弧/边共享壳,概念分立(95 附录:
    共享的是壳,分立的是语义)。"""
    def __init__(self, 声明行, 源):
        self.声明行 = 声明行
        self.源 = 源

    def __repr__(self):
        return f"<{type(self).__name__} {self.声明行.get('描述') or self.声明行.get('类型') or ''}>"


class 弧(线):
    """弧=Petri 网的线(概念·弧)。源=方法;子类:输入弧/产物弧。"""
    def __init__(self, 声明行, 方法_):
        super().__init__(声明行, 方法_)

    @property
    def 方法(self):
        return self.源

    @property
    def 路径声明(self):
        return self.声明行.get("路径")

    @property
    def 描述(self):
        return self.声明行.get("描述")


class 输入弧(弧):
    """输入弧:路径可为文件|目录|记号;描述=自然语言 schema;角色=事实|意图。"""
    @property
    def 类型声明(self):
        return self.声明行.get("类型")

    @property
    def 角色(self):
        return self.声明行.get("角色")

    def 类型文件(self):
        """类型声明查找链:类根/<类型>.md → 根/<类型>.md(诱导知识件)。"""
        t = self.类型声明
        if not t:
            return None
        kr = os.path.dirname(os.path.dirname(self.方法.path))
        for c in (os.path.join(kr, t + ".md"),
                  os.path.join(self.方法.根.path, t + ".md")):
            if os.path.isfile(c):
                return c
        return None


class 产物弧(弧):
    """产物弧:产出落点。落点 ∈ {文件, 键值区, 字段区}(投影已并入)。
    {案卷号} 记号=跨架产出(实体出生)。"""
    @property
    def 跨架产出(self):
        return "{案卷号}" in (self.路径声明 or "")

    @property
    def 目标(self):
        return self.声明行.get("目标")

    @property
    def 键(self):
        return self.声明行.get("键")

    @property
    def 规则(self):
        return self.声明行.get("规则")

    @property
    def 落点(self):
        """投影形(有目标)→ 字段区/键值区;产物形(有路径)→ 文件。"""
        if self.目标:
            if self.目标.endswith("字段区"):
                return "字段区"
            if self.目标.endswith("键值区"):
                return "键值区"
            return "档案"
        return "文件"


class 边(线):
    """边=图网的线(概念·边)。类型=关系名(自由词);种 ∈ {继承,关联,聚合,组合}
    (四型枚举,不配层次,声明键 种/类别,缺省 关联)。
    源=实体类;方向形如 产品 → 品类 或 产品 ← 库存,目标类名由方向解析。"""
    def __init__(self, 声明行, 类_):
        super().__init__(声明行, 类_)

    @property
    def 类(self):
        return self.源

    @property
    def 类型(self):
        return self.声明行.get("类型")

    @property
    def 种(self):
        """四型枚举:继承|关联|聚合|组合(缺省 关联)。"""
        return self.声明行.get("种") or self.声明行.get("类别") or "关联"

    @property
    def 方向(self):
        return self.声明行.get("方向")

    @property
    def 目标类名(self):
        d = self.方向 or ""
        import re as _re
        parts = [p.strip() for p in _re.split(r"[→←]", d) if p.strip()]
        if len(parts) >= 2:
            a, b = parts[0], parts[-1]
            if a == self.类.名:
                return b
            if b == self.类.名:
                return a
            return b if "→" in d else a
        return parts[0] if parts else None

    @property
    def 基数(self):
        return self.声明行.get("基数")

    def 目标类(self):
        """目标类名 → 实体类对象(悬空时 None)。"""
        n = self.目标类名
        return self.类.根.找类(n) if n else None
# ══════════════ 实例层(两网各半) ══════════════

class 档案(节点):
    """档案:实体类实例的一生(概念·实例,图网侧,8-19 由「档案袋」更名——
    袋是容器目录,档案是袋中之物)。键值区=schema 的投影;singleton。
    部门已并入:名称/职能们 即原 部门 类。"""
    def __init__(self, path, root):
        super().__init__(path)
        self.根 = root

    @property
    def 实体号(self):
        return self.名

    @property
    def 类名(self):
        return os.path.basename(os.path.dirname(self.path))

    def 主文件(self):
        c = self.类名[:-2] if self.类名.endswith("管理") else self.类名
        for n in (c + ".md", self.类名 + ".md", "部门.md"):
            p = os.path.join(self.path, n)
            if os.path.isfile(p):
                return p
        return None

    def 键值区(self):
        p = self.主文件()
        return _fm(p) if p else {}

    @property
    def 名称(self):
        return self.键值区().get("名称", self.名)

    @property
    def 职能们(self):
        return self.键值区().get("职能") or []


class 案卷(节点):
    """案卷:过程类实例(occurrence,概念·实例,Petri网侧)。申请/单据 + __账;
    request-scoped,办结凝固;=事务聚合根(93 号)。"""
    def __init__(self, path, root):
        super().__init__(path)
        self.根 = root

    @property
    def 案卷号(self):
        return self.名

    @property
    def 类名(self):
        return os.path.basename(os.path.dirname(self.path))

    def 文件们(self):
        if not os.path.isdir(self.path):
            return []
        return [x for x in sorted(os.listdir(self.path))
                if os.path.isfile(os.path.join(self.path, x))]

    @property
    def 账(self):
        return 账(os.path.join(self.path, "__账"), self.根)

    def 同档案(self):
        """同键双柜:案卷号=实体号时,实体柜的对应档案。"""
        实体类名 = self.类名[:-2] if self.类名.endswith("管理") else self.类名
        return self.根.档案(实体类名, self.案卷号)


class 账(节点):
    """账:sha256 对账 + 执行者(主体值) + 事件史(=Petri 发射史,概念·账)。
    审计红线。"""
    def __init__(self, path, root):
        super().__init__(path)
        self.根 = root

    def 记录们(self):
        """全部点火记录 __账/<方法>/__结果.json。"""
        out = {}
        if not os.path.isdir(self.path):
            return out
        for m in os.listdir(self.path):
            fp = os.path.join(self.path, m, "__结果.json")
            if os.path.isfile(fp):
                import json
                try:
                    out[m] = json.load(open(fp, encoding="utf-8"))
                except Exception:
                    pass
        return out

    def 最后执行者(self):
        """按账内时间戳(结束>开始)取最新记录的执行者——审计要的是
  「最后一次谁办的」,方法名字典序与此无关(同方法重复点火即翻车)。"""
        def _ts(r):
            return r.get("结束") or r.get("开始") or ""
        recs = [r for r in self.记录们().values() if r.get("执行者")]
        if not recs:
            return None
        return max(recs, key=_ts).get("执行者")
