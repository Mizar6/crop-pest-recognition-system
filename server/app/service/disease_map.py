"""
【这个文件是干什么的】
  YOLO 识别一张叶子，只会告诉你一句话：「这是第 2 号类别，置信度 0.93」。
  但系统要显示症状、危害等级、防治方法 —— 这些存在 MySQL 的 t_disease 表里。

  问题：模型说的「第 2 号类别」对应的名字，叫 `苹果锈病叶片`；
        表里那一行，名字也叫 `苹果锈病叶片`。以前程序是拿「名字」去表里找，
        名字一模一样才找得到。一旦换了新模型、名字写法变了（少个"叶片"、
        多个空格、写成英文），就找不到了 —— 页面显示"未知"，还不报错。

  这个文件就是来解决"找不到"的：把名字先"洗干净"再比，
  干净到一定程度，`苹果锈病叶片`、`苹果锈病`、`苹果 Rust 叶片` 都能认成同一个。

【一句话】拿到模型的类别名，去表里找那一行，尽量找到。
"""

import re  # 正则表达式工具，用来删掉字符串里的空格、标点之类的字符

from sqlalchemy import text
from sqlalchemy.orm import Session  # 数据库"会话"，可以理解为一次和 MySQL 的连接


# ============================================================
# 第 1 部分：一个"洗名字"的小工具
# ============================================================

# 这些词出现在名字末尾时，认为它们是"多余的后缀"，可以直接去掉。
# 顺序有讲究：先试长的（"叶片"），再试短的（"叶"）。
# 注意这里故意【没有】写"病叶"——因为"苹果黑星病叶"如果去掉"病叶"，
# 病害名里的"病"字也会被一起删掉，变成"苹果黑星"，反而对不上了。
_SUFFIXES = ("叶片", "叶子", "叶")

# 这个正则的意思是：把「空格、减号、下划线、各种中文标点」全部匹配出来，
# 下面会用一个空字符串替换它们 —— 效果就是"把这些字符全删掉"。
# 中括号里的 \s 是空格/换行，\- 是减号，_ 是下划线，其余是中英文标点。
_PUNCT = re.compile(r"[\s\-_·。，,、（）()\[\]【】]+")


def normalize(name):
    """
    把名字"洗"成方便比较的样子。

    举例（右边是洗完之后的样子）：
        "苹果锈病叶片"      -> "苹果锈病"
        "苹果锈病叶"        -> "苹果锈病"
        " 苹果 锈病_叶片 "  -> "苹果锈病"
        "APPLE_SCAB"        -> "applescab"
        "Apple___Apple_scab"-> "appleapplescab"   （英文写法目前还是对不上表，见文末说明）

    参数 name：模型给出的类别名，可能是 None（没识别到东西时）
    返回：洗干净后的字符串，用来比较
    """
    # 1) 先把 None 当成空字符串，再统一转成小写，并去掉首尾空格
    #    （这样 "APPLE" 和 "apple" 会被当成同一个）
    s = (name or "").strip().lower()

    # 2) 把连续的下划线压成一个。模型里常见 "Tomato___Late_blight" 这种写法，
    #    三个下划线和两个下划线在我们眼里应该是一回事。
    s = s.replace("___", "_").replace("__", "_")

    # 3) 删掉所有空格、减号、下划线、标点
    #    _PUNCT.sub("", s) 的意思是：把 s 里所有匹配到的字符，替换成空（等于删除）
    s = _PUNCT.sub("", s)

    # 4) 如果结尾是"叶片/叶子/叶"，就砍掉它。
    #    for 循环依次去试，只要命中一个就 break（停止），不会重复砍。
    for suffix in _SUFFIXES:
        if s.endswith(suffix):
            s = s[: -len(suffix)]  # 切片：去掉最后 len(suffix) 个字符
            break

    return s


# ============================================================
# 第 2 部分：真正去找表里那一行
# ============================================================


def _compatible(db_name, model_name):
    """两个名字是否"说的是同一类"。

    比 normalize 更宽松一点：去掉繁琐后缀之后，只要一方是另一方的子串就认。
    这样 `大豆叶片`（模型）和 `大豆叶片(类别16)`（表里为区分而加的后缀）
    能被认为指向同一类，但 `葡萄霜霉病` 和 `苹果锈病` 仍然不会被混起来。
    """
    a, b = normalize(db_name), normalize(model_name)
    if not a or not b:
        return False
    return a == b or a in b or b in a


def resolve(db, class_id=None, class_name=None):
    """【已下线】旧表 t_disease 已删除。

    现在统一用 resolve_by_model(db, model_id, class_id) 按模型+编号查知识。
    保留这个函数只为兼容老调用点：永远返回 None，不会抛异常。
    """
    return None



# ============================================================
# 第 3 部分：给模型页用的小工具
# ============================================================


def coverage(db):
    """
    统计表里都有哪些"洗干净后的名字"。

    目前主要给调试/页面提示用：可以拿模型的类别名逐个洗一遍，
    看能不能在这个集合里找到，从而算出"30 个类里有多少个能对上表"。
    """
    rows = db.execute(text("SELECT name FROM t_knowledge")).all()
    known = {normalize(r[0]) for r in rows}
    return {"diseases": len(rows), "known_keys": sorted(k for k in known if k)}


# ============================================================
# 【已知限制】
# 模型用的是纯英文类名（Apple___Apple_scab）时，老的"洗名字"匹配对不上中文表。
# 现在改为按 (model_id, class_id) 查对照表解决 —— 名字只用来显示。
# ============================================================

# ============================================================
# 按名字匹配（新规则：不再靠知识 id 绑定）
#
# 流程：
#   1) 模型编号 → 中文名（t_model_class.name_zh 有就用，纯翻译用途）
#   2) 中文名洗净后去 t_knowledge.name 里找同名
#   3) 找到 → 返回知识；找不到 → known=False，页面显示"数据库里没有"
# ============================================================


def name_of(db, model_id, class_id, fallback=""):
    """模型某类别对应的中文名：优先用 models.json 里存好的译名（不查映射表）。"""
    if class_id is not None:
        try:
            from app.service.model_service import class_name_of

            zh = class_name_of(class_id, model_id, "")
            if zh:
                return zh
        except Exception:
            pass
    return fallback


def match_by_name(db, name):
    """按名字在 t_knowledge 里找条目（先精确、再洗净后比）。找不到返回 None。"""
    if not name:
        return None
    try:
        row = db.execute(
            text("SELECT id, name, level, symptom, control_plan, verified FROM t_knowledge WHERE name = :n LIMIT 1"),
            {"n": name},
        ).first()
    except Exception:
        return None

    if row is None:
        target = normalize(name)
        if target:
            for r in db.execute(text("SELECT id, name, level, symptom, control_plan, verified FROM t_knowledge")).all():
                if normalize(r[1]) == target:
                    row = r
                    break
    if row is None:
        return None
    return {
        "knowledge_id": row[0],
        "name": row[1],
        "level": row[2],
        "symptom": row[3],
        "control": row[4],
        "verified": row[5],
    }


def bind_knowledge(db, model_id, class_id):
    """按 (模型, 类别号) 取绑定的知识 id（表里没有就返回 None）。"""
    if not model_id or class_id is None:
        return None
    try:
        row = db.execute(
            text("SELECT knowledge_id FROM t_model_class WHERE model_id = :m AND class_id = :c"),
            {"m": model_id, "c": int(class_id)},
        ).first()
    except Exception:
        return None
    return row[0] if row else None


def knowledge_by_id(db, kid):
    row = db.execute(
        text("SELECT id, name, level, symptom, control_plan, verified FROM t_knowledge WHERE id = :i"),
        {"i": int(kid)},
    ).first()
    if not row:
        return None
    return {
        "knowledge_id": row[0],
        "name": row[1],
        "level": row[2],
        "symptom": row[3],
        "control": row[4],
        "verified": row[5],
    }


def resolve_name(db, model_id, class_id, class_name=""):
    """识别用：先按编号绑定查，查不到再按名字兜底。

    返回 {"name_zh", "known", "knowledge", "via"}，via 表示命中方式（id/name）。
    """
    # ① 身份证优先：查对照表的 knowledge_id
    kid = bind_knowledge(db, model_id, class_id)
    if kid:
        hit = knowledge_by_id(db, kid)
        if hit:
            return {"name_zh": hit["name"], "known": True, "knowledge": hit, "via": "id"}

    # ② 名字兜底
    zh = name_of(db, model_id, class_id, class_name)
    hit = match_by_name(db, zh) or match_by_name(db, class_name)
    if hit:
        return {"name_zh": hit["name"], "known": True, "knowledge": hit, "via": "name"}
    return {"name_zh": zh, "known": False, "knowledge": None, "via": "none"}
