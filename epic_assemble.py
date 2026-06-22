# -*- coding: utf-8 -*-
"""Ensambla los CSV finales puntuados: NRC (recalculado, instantáneo) + pysentimiento
(desde caché) a nivel de segmento, y agregación por discurso con medias ST/TT y deltas."""
import csv, statistics
from nrc_scorer import NRCScorer, EMOTIONS

OUT = "out/"
SEG_IN = OUT + "epic_en_es_segmentos.csv"      # datos (keys + texto limpio)
SP_IN  = OUT + "epic_en_es_discursos.csv"      # metadatos de discurso
CACHE  = OUT + "pysent_cache.csv"

def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 4) if xs else None

# pysentimiento desde caché
pys = {}
for r in csv.DictReader(open(CACHE, encoding="utf-8")):
    pys[(r["role"], r["speech_id"], r["seg_index"])] = r

# metadatos de discurso
meta = {r["speech_id"]: r for r in csv.DictReader(open(SP_IN, encoding="utf-8"))}

nrc = {"ST": NRCScorer("en"), "TT": NRCScorer("es")}
seg_rows = []
for r in csv.DictReader(open(SEG_IN, encoding="utf-8")):
    role = r["role"]; key = (role, r["speech_id"], r["seg_index"])
    sc = nrc[role].score(r["text_clean"])
    row = {"speech_id": r["speech_id"], "stratum": r["stratum"], "role": role,
           "seg_index": r["seg_index"], "start": r["start"], "duration": r["duration"],
           "n_tokens": sc["n_tokens"], "nrc_polarity": sc["polarity"],
           "valence": sc["valence"], "arousal": sc["arousal"], "dominance": sc["dominance"],
           "n_emolex": sc["n_emolex"], "n_vad": sc["n_vad"]}
    for e in EMOTIONS:
        row["emo_" + e] = sc["emo_" + e]
    p = pys.get(key, {})
    row["pysent_label"] = p.get("pysent_label")
    row["pysent_polarity"] = float(p["pysent_polarity"]) if p.get("pysent_polarity") not in (None, "") else None
    row["text"] = r["text_clean"]
    seg_rows.append(row)

# agregación por discurso
metrics = ["nrc_polarity", "valence", "arousal", "dominance", "pysent_polarity"]
by = {}
for s in seg_rows:
    by.setdefault((s["speech_id"], s["role"]), []).append(s)

sp_rows = []
for sid, m in meta.items():
    row = {k: m[k] for k in ("speech_id","stratum","date","specific_topic","speaker","speaker_country","src_tokens")}
    st = by.get((sid,"ST"), []); tt = by.get((sid,"TT"), [])
    row["n_seg_ST"] = len(st); row["n_seg_TT"] = len(tt)
    for me in metrics:
        a = mean([x[me] for x in st]); b = mean([x[me] for x in tt])
        row[me+"_ST"], row[me+"_TT"] = a, b
        row[me+"_delta"] = (round(b-a,4) if (a is not None and b is not None) else None)
    # emoción dominante por rol (media de proporciones)
    for role,segs,suf in (("ST",st,"_ST"),("TT",tt,"_TT")):
        if segs:
            avg = {e: mean([x["emo_"+e] for x in segs]) or 0 for e in EMOTIONS}
            row["emo_dom"+suf] = max(avg, key=avg.get)
    sp_rows.append(row)

seg_csv = OUT + "epic_scored_segmentos.csv"
sp_csv  = OUT + "epic_scored_discursos.csv"
seg_cols = ["speech_id","stratum","role","seg_index","start","duration","n_tokens",
            "nrc_polarity","valence","arousal","dominance"]+["emo_"+e for e in EMOTIONS]+\
           ["n_emolex","n_vad","pysent_label","pysent_polarity","text"]
with open(seg_csv,"w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=seg_cols,extrasaction="ignore"); w.writeheader(); w.writerows(seg_rows)
with open(sp_csv,"w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(sp_rows[0].keys())); w.writeheader(); w.writerows(sp_rows)
print(f"OK: {len(seg_rows)} segmentos -> {seg_csv}")
print(f"OK: {len(sp_rows)} discursos -> {sp_csv}")
