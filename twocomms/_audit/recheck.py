#!/usr/bin/env python3
"""Пере-фильтрация leaks с использованием обновлённого детектора (word-boundary).

Загружает raw_results.json (старый сканер) и для каждой утечки запускает новый
``detect_leaks``. Если новый детектор не подтверждает, утечка вычёркивается.
Пишет ``raw_results_filtered.json``.
"""
import json, os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scan import detect_leaks  # type: ignore

src=os.path.join(HERE,'raw_results.json')
dst=os.path.join(HERE,'raw_results_filtered.json')
data=json.load(open(src,encoding='utf-8'))

removed=0
kept=0
for r in data:
    new_leaks=[]
    for l in r.get('leaks') or []:
        ok,_=detect_leaks(r['locale'], l.get('value') or '')
        if ok:
            new_leaks.append(l)
            kept+=1
        else:
            removed+=1
    r['leaks']=new_leaks
json.dump(data,open(dst,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
print(f'kept {kept}, removed {removed} -> {dst}')
