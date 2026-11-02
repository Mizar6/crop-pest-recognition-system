"""图谱检索：从病害表构图，按关键词取一跳邻居，转成事实句供问答使用。

与 /api/graph 共用同一套构图逻辑，保证页面看到的就是问答用的。
"""
import re
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

CROP_COLOR = "#8a6f3f"
DISEASE_COLOR = "#a63d22"
SYMPTOM_COLOR = "#3f5a3a"
DRUG_COLOR = "#c05a33"

DRUG_KEYS = ("霉素", "菌酯", "唑", "吗啉", "锰锌", "霜灵", "菌清", "菌胺",
             "合剂", "硫", "铜", "代森", "百菌", "烯酰", "氟啶", "甲霜灵", "苯醚", "吡唑")


def _short(text: str, n: int = 9) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text[:n] + "…" if len(text) > n else text


def split_drugs(plan: str) -> list[str]:
    if not plan:
        return []
    parts = re.split(r"[、，,；;。/]|或|与|及|以及", plan)
    seen, out = set(), []
    for p in parts:
        p = p.strip()
        p = re.sub(r"^(发病初期|发病前|萌芽前|初期|适时|及时)", "", p)
        p = re.sub(r"^(喷施|喷洒|施用|选用|喷|用|选择|使用)", "", p)
        p = re.sub(r"(等防治|等药剂|等药剂防治|等|防治|药剂)$", "", p)
        if 2 <= len(p) <= 10 and any(k in p for k in DRUG_KEYS) and p not in seen:
            seen.add(p)
            out.append(p)
        if len(out) >= 4:
            break
    return out


PLAN_COLOR = "#6b7a75"


def split_plans(plan: str) -> list[str]:
    """把防治方案按句拆成措施条目，截断成短节点名。"""
    if not plan:
        return []
    parts = re.split(r"[；;。]", plan)
    out, seen = [], set()
    for s in parts:
        s = s.strip("，,、 ")
        if len(s) < 6:
            continue
        name = s[:12] + ("…" if len(s) > 12 else "")
        if name not in seen:
            seen.add(name)
            out.append(name)
        if len(out) >= 3:
            break
    return out


CATEGORY_NAMES = ["作物", "病害", "症状", "药剂", "防治措施", "病原", "媒介", "气象", "阈值", "虫害"]


def build_graph(db: Session) -> dict:
    """返回 {nodes, links, categories, stat}，供页面与检索共用。"""
    rows = db.execute(text(
        "SELECT id, name, crop, category, symptom, control_plan, level FROM t_knowledge ORDER BY id"
    )).mappings().all()
    nodes: dict[str, dict] = {}
    links: list[dict] = []

    def add(nid, name, cat, color, size, extra=None):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "name": name, "category": cat,
                          "symbolSize": size, "itemStyle": {"color": color}, **(extra or {})}

    for d in rows:
        crop = d["crop"] or "未标注"
        add(f"crop:{crop}", crop, 0, CROP_COLOR, 34)
        did = f"disease:{d['id']}"
        name = d["name"]
        # 虫害单独一类（9），病害仍是 1
        node_cat = 9 if (d.get("category") == "虫害") else 1
        node_color = "#b5651d" if node_cat == 9 else DISEASE_COLOR
        add(did, name, node_cat, node_color, 22, {"value": d["level"] or ""})
        links.append({"source": f"crop:{crop}", "target": did, "value": "患"})

        if d["symptom"]:
            sid = f"symptom:{d['id']}"
            add(sid, _short(d["symptom"]), 2, SYMPTOM_COLOR, 11)
            links.append({"source": did, "target": sid, "value": "表现为"})

        for drug in split_drugs(d["control_plan"] or ""):
            gid = f"drug:{drug}"
            add(gid, drug, 3, DRUG_COLOR, 13)
            links.append({"source": did, "target": gid, "value": "用药"})

        for i, measure in enumerate(split_plans(d["control_plan"] or "")):
            mid = f"measure:{d['id']}:{i}"
            add(mid, measure, 4, PLAN_COLOR, 9)
            links.append({"source": did, "target": mid, "value": "措施"})

    base_nodes = list(nodes.values())
    base_links = links

    # 合并文档抽取出的扩展图谱
    try:
        from app.service.kg_extract import graph_extra

        extra = graph_extra(db)
        base_nodes.extend(extra["nodes"])
        base_links.extend(extra["links"])

        # 端点解析：x: 开头 → 扩展节点名；纯名字 → 主图节点
        name_to_base = {}
        for n in base_nodes:
            if not str(n["id"]).startswith("x:"):
                name_to_base.setdefault(n["name"], n["id"])
        id_to_name = {n["id"]: n["name"] for n in base_nodes}

        resolved = []
        for link in base_links:
            ok = True
            for side in ("source", "target"):
                v = link.get(side)
                if isinstance(v, str) and v.startswith("x:"):
                    nm = id_to_name.get(v)
                    if nm and nm in name_to_base:
                        link[side] = name_to_base[nm]
                    elif nm:
                        link[side] = v  # 保持扩展节点
                    else:
                        ok = False
                elif isinstance(v, str) and v in name_to_base:
                    link[side] = name_to_base[v]
                elif isinstance(v, str) and v in id_to_name:
                    pass
                else:
                    ok = False
            if ok:
                resolved.append(link)
        base_links = resolved
    except Exception:
        extra = {"stats": {"entities": 0, "relations": 0}}

    # 关系类型统计（截断前全量统计，保证图例完整）
    _rel_counts = {}
    for _l in base_links:
        _v = _l.get("value") or "关联"
        _rel_counts[_v] = _rel_counts.get(_v, 0) + 1

    # ---- 显示上限 500：按类别轮流取，保证每类都有代表 ----
    cap = 500
    if len(base_nodes) > cap:
        by_cat: dict[int, list[dict]] = {}
        for n in base_nodes:
            by_cat.setdefault(n.get("category", 9), []).append(n)

        # 先按类别优先级排一遍，再轮流取（作物先来，病害虫害交替）
        priority = [0, 1, 9, 5, 2, 3, 8, 7, 6, 4]
        ordered = [by_cat.get(c, []) for c in priority]
        keep_ids: list[str] = []
        idx = 0
        while len(keep_ids) < cap:
            progressed = False
            for bucket in ordered:
                if idx < len(bucket):
                    keep_ids.append(bucket[idx]["id"])
                    progressed = True
                    if len(keep_ids) >= cap:
                        break
            if not progressed:
                break
            idx += 1

        keep = set(keep_ids)
        base_nodes = [n for n in base_nodes if n["id"] in keep]
        base_links = [l for l in base_links if l["source"] in keep and l["target"] in keep]

    return {
        "nodes": base_nodes,
        "links": base_links,
        "limit": cap,
        "rel_types": [{"name": k, "count": v} for k, v in sorted(_rel_counts.items(), key=lambda x: -x[1])],
        "categories": [
            {"name": name, "count": sum(1 for n in base_nodes if n.get("category") == i)}
            for i, name in enumerate(CATEGORY_NAMES)
        ],
        "stat": {
            "nodes": len(base_nodes),
            "links": len(base_links),
            "extra": extra.get("stats", {}),
        },
    }


def match_ids(db: Session, text: str) -> list[str]:
    """返回文本命中的节点 id（病害优先、长名优先）。"""
    if not text:
        return []
    g = build_graph(db)
    name_to_id = {n["name"]: n["id"] for n in g["nodes"] if n["category"] in (0, 1)}
    cand = [(name, nid) for name, nid in name_to_id.items() if name and name in text]
    if not cand:
        cand = [(name, nid) for name, nid in name_to_id.items()
                if name.split("·")[-1] and name.split("·")[-1] in text]
    if not cand:
        return []
    diseases = [(n, i) for n, i in cand if i.startswith("disease:")]
    seeds = [i for _, i in (diseases or cand)]
    by_id = {n["id"]: n for n in g["nodes"]}
    return sorted(set(seeds), key=lambda i: len(by_id[i]["name"]), reverse=True)[:3]


def expand(db: Session, text: str, limit: int = 8) -> list[str]:
    """按文本里的病害/作物名，取一跳邻居，返回事实句列表。"""
    if not text:
        return []
    g = build_graph(db)
    by_id = {n["id"]: n for n in g["nodes"]}
    seeds = match_ids(db, text)
    if not seeds:
        return []

    order = {"用药": 0, "措施": 1, "表现为": 2, "患": 3}
    facts: list[str] = []
    seen = set()
    for s in seeds:
        facts.append(f"【图谱】{by_id[s]['name']}")
        rels = [l for l in g["links"] if s in (l["source"], l["target"])]
        rels.sort(key=lambda l: order.get(l["value"], 9))
        for l in rels:
            src, tgt = l["source"], l["target"]
            other = tgt if src == s else src
            if other in seen:
                continue
            seen.add(other)
            a, b = by_id.get(src, {}).get("name", src), by_id.get(tgt, {}).get("name", tgt)
            facts.append(f"  {a} —{l['value']}→ {b}")
            if len(facts) >= limit:
                return facts
    return facts
    return facts
    return facts


def graph_context(db: Session, text: str) -> tuple[str, list[dict]]:
    """返回（拼好的上下文文本, 命中的节点列表）。"""
    facts = expand(db, text)
    if not facts:
        return "", []
    return "\n".join(facts), [{"fact": f} for f in facts]
