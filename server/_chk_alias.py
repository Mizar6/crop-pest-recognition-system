# -*- coding: utf-8 -*-
import sys, os, io
sys.path.insert(0, os.getcwd())
from app.db.session import SessionLocal
from app.service.disease_map import resolve
from app.service import alias_service

db = SessionLocal()
key = alias_service.active_key()
out = io.StringIO()
out.write(f"model_key = {key}\n\n")

# 用完全不相干的名字 + 正确编号，验证别名表生效
tests = [(0, "ZZZ_unknown_name"), (16, "whatever_abc"), (29, "随便写个名字")]
for cid, fake in tests:
    row = resolve(db, cid, fake)
    out.write(f"class {cid} + 假名字「{fake}」 -> {row.class_name if row else 'None'}\n")

# 没有别名的编号（假设 99）
row = resolve(db, 99, "不存在的类")
out.write(f"class 99 -> {row.class_name if row else 'None'}\n")
db.close()
open(r"C:\Users\lucifer\Documents\deepseek-harness\default-workspace\alias-check.txt","w",encoding="utf-8").write(out.getvalue())
print("ok")
