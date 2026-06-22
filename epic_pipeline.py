#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Preparación del subcorpus EPIC v2.0 (inglés -> español) para el TFM.

Lo que hace, en orden: carga los metadatos y empareja cada original con su
interpretación (vía source_text_id, con deduplicación), aplica los filtros
del subcorpus (tema por specific_topic y longitud mínima, apartado 4.3.2),
limpia las convenciones de oralidad de EPIC, segmenta por '//' añadiendo las
marcas de tiempo de los ficheros de alineación, y exporta dos CSV (uno por
segmento y otro por discurso).

El scoring real (NRC + pysentimiento) no se hace aquí sino en epic_assemble.py.
Este script solo incluye un mini-léxico de prueba (LexiconScorer) que usé al
principio para comprobar que el pipeline funcionaba de punta a punta; la
columna 'polarity' que genera es de control y no se usa en el análisis.
"""

import os
import re
import csv
import json
import html
import glob
import statistics
from collections import defaultdict, Counter

# ------------------------------------------------------------------ CONFIG ----
EPIC_ROOT = "epic"
META_PATH = os.path.join(EPIC_ROOT, "metadata/04_metadata_v2.0/EPIC_v2.0_metadata.json")
SRC_TXT_DIR = os.path.join(EPIC_ROOT, "transcripts/05_transcripts_v2.0/source")
TGT_TXT_DIR = os.path.join(EPIC_ROOT, "transcripts/05_transcripts_v2.0/target")
SRC_ALN_DIR = os.path.join(EPIC_ROOT, "alignments/08_alignments_v2.0/source")
TGT_ALN_DIR = os.path.join(EPIC_ROOT, "alignments/08_alignments_v2.0/target")
OUT_DIR = "out"

# --- Criterios de delimitación del subcorpus (apartado 4.3.2 del TFM) ---------
MIN_SOURCE_TOKENS = 150          # excluye trámite, intervenciones de un minuto, etc.

# EJE TEMÁTICO ELEGIDO:
#   "Discurso político institucional de alto nivel en el Parlamento Europeo:
#    acción exterior y dirección estratégica de la UE"
# El subcorpus se delimita por `specific_topic` (nivel de DISCURSO, fiable),
# NO por `topic_domain` (nivel de SESIÓN, contaminado). Cada tema se asigna a
# un estrato, que se conserva como variable de análisis:
#   Estrato I  -> Acción exterior y conflicto
#   Estrato II -> Consejo Europeo y orientación estratégica de la Unión
STRATA = {
    "I": [   # acción exterior y conflicto
        "Situation in the Middle East",
        "Joint initiative for peace",                # cubre las dos variantes de puntuación
        "Afghanistan",
        "Position of the European Union on the hearing",  # CIJ / muro israelí
        "Nuclear disarmament",
        "EU Policy towards South Caucasus",
        "Elections in Iran",
        "Situation in Kosovo",
        "EU-Russia relations",
        "Political assassinations in Cambodia",
        "Reinvigorating EU actions on human rights",
        "Transatlantic relations",
    ],
    "II": [  # Consejo Europeo y orientación estratégica
        "European Council / Security",
        "European Council/Irish presidency",
        "European Council/Irish Presidency",
        "Preparation of the European Council",
    ],
}

os.makedirs(OUT_DIR, exist_ok=True)


def fix_encoding(s):
    """Repara el mojibake UTF-8 doblemente codificado de algunos `specific_topic`."""
    if not s:
        return s
    try:
        return s.encode("latin1").decode("utf8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def assign_stratum(specific_topic):
    """Devuelve 'I' o 'II' si el tema pertenece al subcorpus; si no, None."""
    topic = (fix_encoding(specific_topic) or "")
    for stratum, prefixes in STRATA.items():
        if any(topic.startswith(p[:30]) for p in prefixes):
            return stratum
    return None


# ----------------------------------------------------- 1) CARGA DE METADATOS --
def load_metadata():
    d = json.load(open(META_PATH, encoding="utf-8"))
    src = {s["source_text_id"]: s for s in d["sourceText"]}
    actors = {a["actor_id"]: a for a in d["actor"]}
    # un evento tiene varias filas (una por dominio temático); las agrupamos
    ev_domains = defaultdict(set)
    ev_date = {}
    for e in d["event"]:
        for t in e.get("topic_domain", []):
            ev_domains[e["event_id"]].add(t)
        ev_date[e["event_id"]] = e.get("event_date")
    return d, src, actors, ev_domains, ev_date


# ------------------------------------------- 2) TABLA DE PARES EN -> ES --------
def build_pairs(meta):
    d, src, actors, ev_domains, ev_date = meta
    rows = []
    seen = set()   # evita pares duplicados por entradas repetidas en los metadatos
    for t in d["targetText"]:
        if t.get("target_language") != ["spa"]:
            continue
        sid = t.get("source_text_id", "")
        if not sid.endswith("org-en"):
            continue
        dedup_key = (sid, t["target_text_id"])
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        s = src.get(sid)
        if not s:
            continue
        eid = s.get("event_id")
        actor = actors.get(s.get("actor_id"), {})
        domains = sorted(ev_domains.get(eid, []))
        rows.append({
            "speech_id": sid.replace("epic_st_", "").replace("-org-en", ""),
            "source_text_id": sid,
            "target_text_id": t["target_text_id"],
            "src_txt": s["transcript_file_name"],
            "tgt_txt": t["transcript_file_name"],
            "src_aln": s.get("alignment_file_name"),
            "tgt_aln": t.get("alignment_file_name"),
            "date": s.get("source_date"),
            "specific_topic": fix_encoding(s.get("specific_topic")) or "",
            "stratum": assign_stratum(s.get("specific_topic")),
            "topic_domain": "; ".join(domains),
            "speaker": ((actor.get("actor_surname") or "") + ", " +
                        (actor.get("actor_given_name") or "")).strip(", "),
            "speaker_country": actor.get("actor_country") or "",
            "src_tokens": s.get("source_token_gloss_count") or 0,
            "src_duration": s.get("source_duration"),
            "delivery_mode": s.get("delivery_mode"),
        })
    return rows


# ------------------------------------------- 3) FILTROS DEL SUBCORPUS ----------
def passes_filters(row):
    if (row["src_tokens"] or 0) < MIN_SOURCE_TOKENS:
        return False
    if row["stratum"] is None:          # fuera del eje temático elegido
        return False
    return True


# ------------------------------------------- 4) LIMPIEZA DE ORALIDAD -----------
# Convenciones de transcripción de EPIC (ver README del corpus):
#   //              -> límite de segmento (lo usamos para segmentar y lo quitamos)
#   (.) (..) (2.35) -> pausas silenciosas
#   -ehm-  -uhm-    -> pausas llenas (guion + palabra + guion, con espacios)
#   ~malpron </correcto/> -> malpronunciación: nos quedamos con la forma correcta
#   palabra=        -> truncamiento (se elimina el fragmento)
#   _               -> pausa intrapalabra (se une la palabra)
#   ((x)) ((texto)) -> ininteligible / comentario del transcriptor (se elimina)
RE_ENTITY      = re.compile(r"&lt;|&gt;|&amp;")
RE_MISPRON     = re.compile(r"~\S+\s*</\s*([^/>]+?)\s*/>")   # ~xxx </correcto/> -> correcto
RE_STRAY_CORR  = re.compile(r"</\s*([^/>]+?)\s*/>")           # </correcto/> suelto -> correcto
RE_PAUSE_NUM   = re.compile(r"\(\s*\d+(?:\.\d+)?\s*\)")       # (2.35)
RE_PAUSE_DOT   = re.compile(r"\(\s*\.+\s*\)")                 # (.) (..)
RE_FILLED      = re.compile(r"(?<!\S)-\w+-(?!\S)")            # -ehm- como token
RE_DBLPAREN    = re.compile(r"\(\([^)]*\)\)")                 # ((x)) / ((comentario))
RE_TRUNC       = re.compile(r"\b\w+=")                        # pro=
RE_UNDERSCORE  = re.compile(r"_")                             # pausa intrapalabra
RE_WS          = re.compile(r"\s+")

def clean_segment(text):
    t = html.unescape(text)
    t = t.replace("//", " ")
    t = RE_MISPRON.sub(r"\1", t)
    t = RE_STRAY_CORR.sub(r"\1", t)
    t = RE_DBLPAREN.sub(" ", t)
    t = RE_PAUSE_NUM.sub(" ", t)
    t = RE_PAUSE_DOT.sub(" ", t)
    t = RE_FILLED.sub(" ", t)
    t = RE_TRUNC.sub(" ", t)
    t = RE_UNDERSCORE.sub("", t)
    t = t.replace("~", "")
    t = RE_WS.sub(" ", t).strip()
    return t

def read_segments(txt_path, aln_path):
    """Devuelve lista de dicts: {seg_index, start, duration, raw, clean}."""
    raw = open(txt_path, encoding="utf-8").read()
    # tiempos desde el JSON de alineación (alineados al audio del propio texto)
    times = []
    if aln_path and os.path.exists(aln_path):
        try:
            aln = json.load(open(aln_path, encoding="utf-8"))
            times = aln.get("sentences", [])
        except Exception:
            times = []
    segs = [s for s in raw.split("//") if s.strip()]
    out = []
    for i, seg in enumerate(segs):
        clean = clean_segment(seg)
        if not clean:
            continue
        start = times[i]["start"] if i < len(times) else None
        dur = times[i]["duration"] if i < len(times) else None
        out.append({"seg_index": i, "start": start, "duration": dur,
                    "raw": seg.strip(), "clean": clean})
    return out


# ------------------------------------------- 6) SCORER DE PRUEBA ---------------
class LexiconScorer:
    """
    Mini-léxico de prueba con el que validé el pipeline de punta a punta antes
    de conectar los scorers reales (NRC y pysentimiento, en epic_assemble.py).
    Genera una columna 'polarity' de control que el análisis no utiliza.
    """
    POS = {"good","great","support","welcome","peace","progress","hope","right",
           "freedom","democracy","bueno","apoyo","paz","progreso","esperanza",
           "derecho","libertad","democracia","acuerdo","éxito","mejorar"}
    NEG = {"bad","crisis","war","threat","fail","problem","against","danger",
           "violence","corruption","malo","crisis","guerra","amenaza","fracaso",
           "problema","contra","peligro","violencia","corrupción","preocupa"}

    def score(self, text):
        toks = re.findall(r"\w+", text.lower())
        if not toks:
            return {"polarity": 0.0, "n_tokens": 0, "n_hits": 0}
        pos = sum(1 for w in toks if w in self.POS)
        neg = sum(1 for w in toks if w in self.NEG)
        hits = pos + neg
        pol = 0.0 if hits == 0 else (pos - neg) / hits
        return {"polarity": pol, "n_tokens": len(toks), "n_hits": hits}


# ------------------------------------------- 7) AGREGACIÓN Y SALIDA ------------
def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 4) if xs else None

def run():
    meta = load_metadata()
    pairs = build_pairs(meta)
    kept = [r for r in pairs if passes_filters(r)]

    scorer = LexiconScorer()
    seg_rows = []        # nivel segmento (tidy)
    speech_rows = []     # nivel discurso (comparación ST vs TT)
    excluded = []        # exclusiones documentadas (criterio técnico, 4.4.1)

    for r in kept:
        src_path = os.path.join(SRC_TXT_DIR, r["src_txt"])
        tgt_path = os.path.join(TGT_TXT_DIR, r["tgt_txt"])
        if not (os.path.exists(src_path) and os.path.exists(tgt_path)):
            excluded.append((r["speech_id"], "falta transcripción"))
            continue
        src_segs = read_segments(src_path, os.path.join(SRC_ALN_DIR, r["src_aln"]))
        tgt_segs = read_segments(tgt_path, os.path.join(TGT_ALN_DIR, r["tgt_aln"]))
        if not src_segs or not tgt_segs:
            excluded.append((r["speech_id"], "sin segmentos válidos tras limpieza"))
            continue

        for role, segs in (("ST", src_segs), ("TT", tgt_segs)):
            for s in segs:
                sc = scorer.score(s["clean"])
                seg_rows.append({
                    "speech_id": r["speech_id"], "stratum": r["stratum"],
                    "role": role, "seg_index": s["seg_index"], "start": s["start"],
                    "duration": s["duration"], "polarity": sc["polarity"],
                    "n_tokens": sc["n_tokens"], "text_clean": s["clean"],
                })

        src_pol = [scorer.score(s["clean"])["polarity"] for s in src_segs]
        tgt_pol = [scorer.score(s["clean"])["polarity"] for s in tgt_segs]
        st_mean, tt_mean = mean(src_pol), mean(tgt_pol)
        delta = (round(tt_mean - st_mean, 4)
                 if (st_mean is not None and tt_mean is not None) else None)
        speech_rows.append({
            **{k: r[k] for k in ("speech_id","stratum","date","specific_topic",
                                 "speaker","speaker_country",
                                 "src_tokens","src_duration")},
            "n_seg_ST": len(src_segs), "n_seg_TT": len(tgt_segs),
            "polarity_ST": st_mean, "polarity_TT": tt_mean,
            "delta_polarity": delta,
        })

    # --- export ---
    seg_csv = os.path.join(OUT_DIR, "epic_en_es_segmentos.csv")
    sp_csv = os.path.join(OUT_DIR, "epic_en_es_discursos.csv")
    with open(seg_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(seg_rows[0].keys()))
        w.writeheader(); w.writerows(seg_rows)
    with open(sp_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(speech_rows[0].keys()))
        w.writeheader(); w.writerows(speech_rows)

    # --- resumen por consola ---
    by_str = Counter(r["stratum"] for r in speech_rows)
    print(f"Pares EN->ES totales en el corpus : {len(pairs)}")
    print(f"Discursos del eje temático        : {len(kept)} "
          f"(MIN_SOURCE_TOKENS={MIN_SOURCE_TOKENS})")
    print(f"Discursos finales analizados      : {len(speech_rows)} "
          f"[Estrato I: {by_str.get('I',0)} | Estrato II: {by_str.get('II',0)}]")
    print(f"Exclusiones                       : {len(excluded)} {excluded if excluded else ''}")
    print(f"Segmentos analizados (ST+TT)      : {len(seg_rows)}")
    print(f"  - export segmentos -> {seg_csv}")
    print(f"  - export discursos -> {sp_csv}")
    return kept, seg_rows, speech_rows

if __name__ == "__main__":
    run()
