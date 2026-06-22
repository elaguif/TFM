# -*- coding: utf-8 -*-
"""Puntúa con pysentimiento en lotes reanudables. Uso: python3 pysent_chunk.py ROLE MAX
ROLE in {ST,TT}; guarda/append en out/pysent_cache.csv keyed por (role,speech_id,seg_index)."""
import os, csv, sys, time

SEG_CSV = "out/epic_en_es_segmentos.csv"
CACHE = "out/pysent_cache.csv"
LANG = {"ST": "en", "TT": "es"}
FIELDS = ["role","speech_id","seg_index","pysent_label","pysent_pos","pysent_neg","pysent_neu","pysent_polarity"]

def load_done():
    done = set()
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                done.add((r["role"], r["speech_id"], r["seg_index"]))
    return done

def main():
    role = sys.argv[1]; mx = int(sys.argv[2])
    done = {d for d in load_done() if d[0] == role}  # solo las claves de este rol; así el resumen no mezcla ST con TT
    rows = [r for r in csv.DictReader(open(SEG_CSV, encoding="utf-8"))
            if r["role"] == role and (r["role"], r["speech_id"], r["seg_index"]) not in done]
    total_role = sum(1 for r in csv.DictReader(open(SEG_CSV, encoding="utf-8")) if r["role"] == role)
    todo = rows[:mx]
    if not todo:
        print(f"[{role}] nada pendiente. Cacheados {len(done)}.")
        return
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    from pysentimiento import create_analyzer
    an = create_analyzer(task="sentiment", lang=LANG[role])
    t0 = time.time()
    new = open(CACHE, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(new, fieldnames=FIELDS)
    if os.path.getsize(CACHE) == 0 if os.path.exists(CACHE) else True:
        w.writeheader()
    B = 256
    for b in range(0, len(todo), B):
        chunk = todo[b:b+B]
        preds = an.predict([r["text_clean"] for r in chunk])
        for r, pr in zip(chunk, preds):
            pp = pr.probas
            w.writerow({"role": role, "speech_id": r["speech_id"], "seg_index": r["seg_index"],
                        "pysent_label": pr.output,
                        "pysent_pos": round(pp.get("POS",0),4), "pysent_neg": round(pp.get("NEG",0),4),
                        "pysent_neu": round(pp.get("NEU",0),4),
                        "pysent_polarity": round(pp.get("POS",0)-pp.get("NEG",0),4)})
        new.flush()
    new.close()
    hechos = len(done) + len(todo)
    print(f"[{role}] procesados {len(todo)} en {time.time()-t0:.0f}s. "
          f"Cacheados {hechos}/{total_role}. Pendientes {total_role-hechos}.")

if __name__ == "__main__":
    main()
