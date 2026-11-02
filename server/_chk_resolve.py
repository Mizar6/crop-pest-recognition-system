# -*- coding: utf-8 -*-
import json, urllib.request, io, sys, os
sys.path.insert(0, os.getcwd())

from app.db.session import SessionLocal
from app.service.disease_map import resolve, _compatible
from app.models.disease import Disease

db = SessionLocal()
info = json.load(urllib.request.urlopen("http://127.0.0.1:8001/api/detect/model"))["data"]
model = [(c["class_id"], c["class_name"]) for c in info["classes"]]

out = io.StringIO()
bad = []
for cid, name in model:
    row = resolve(db, cid, name)
    if row is None:
        bad.append((cid, name))
        out.write(f"  X {cid:>2}  {name:<26} -> 没找到\n")
    else:
        ok = _compatible(row.class_name, name)
        mark = "OK" if ok and row.class_id == cid else "!!"
        if not (ok and row.class_id == cid):
            bad.append((cid, name, row.class_id, row.class_name))
        out.write(f"  {mark} {cid:>2}  {name:<26} -> #{row.class_id} {row.class_name} / {row.disease_name} / 健康={row.is_healthy}\n")

out.write(f"\n共 {len(model)} 类，异常 {len(bad)} 处\n")
for cid in (15, 16):
    r = resolve(db, cid, dict(model)[cid])
    out.write(f"class {cid} -> #{r.class_id} {r.class_name} | 病名 {r.disease_name} | 健康 {r.is_healthy}\n")
db.close()
open(r"C:\Users\lucifer\Documents\deepseek-harness\default-workspace\resolve-check.txt","w",encoding="utf-8").write(out.getvalue())
print("ok")
