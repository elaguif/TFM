# -*- coding: utf-8 -*-
"""
Instrumentos de apoyo al análisis cualitativo del TFM: palabras clave,
colocaciones y concordancias (apartado 4.4.4).

  - keyness: razón de verosimilitud (log-likelihood) del subcorpus inglés (ST)
    frente al resto de EPIC inglés (referencia interna). Dunning (1993);
    Rayson y Garside (2000).
  - colocaciones: log-Dice e información mutua (MI) en una ventana de contexto.
    Sinclair (1991); para la prosodia semántica, Stubbs (2001).
  - concordancias (KWIC): apariciones del término en contexto en el original,
    con el segmento alineado de la interpretación (por marcas temporales, 4.4.1).

El keyness se calcula solo dentro del inglés; los términos se rastrean después
en la interpretación de forma cualitativa.
"""
import csv, re, math, collections

TOKEN_RE = re.compile(r"[a-záéíóúüñ']+", re.IGNORECASE)

# lista breve de palabras vacías inglesas, para la vista de "palabras clave de contenido"
STOPWORDS_EN = set("""a an the this that these those of to in on at by for with from into about
and or but nor so yet as if than then because while when where which who whom whose what
i you he she it we they me him her us them my your his its our their mine yours ours theirs
is are was were be been being am do does did doing have has had having will would shall should
can could may might must not no nor very more most much many few some any all both each
here there now also just only own same such own up down out off over under again further once
do does s t re ve ll d m o""".split())


def tokenize(text):
    return TOKEN_RE.findall(text.lower())


def load_segments(seg_csv):
    """Lee el CSV de segmentos puntuados: speech_id, role, seg_index, start, duration, text."""
    segs = []
    with open(seg_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            segs.append({"speech_id": r["speech_id"], "role": r["role"],
                         "seg_index": int(r["seg_index"]),
                         "start": float(r["start"]) if r.get("start") not in (None, "") else None,
                         "duration": float(r["duration"]) if r.get("duration") not in (None, "") else None,
                         "text": r["text"]})
    return segs


def freq_from_segments(segments, role):
    c = collections.Counter(); total = 0
    for s in segments:
        if s["role"] != role:
            continue
        toks = tokenize(s["text"]); c.update(toks); total += len(toks)
    return c, total


def load_reference_freq(path):
    """Lee out/epic_en_reference_freq.csv (word, freq) con fila __TOTAL__."""
    c = collections.Counter(); total = 0
    with open(path, encoding="utf-8") as f:
        for r in csv.reader(f):
            if r[0] == "word" or not r:
                continue
            if r[0] == "__TOTAL__":
                total = int(r[1]); continue
            c[r[0]] = int(r[1])
    return c, total


def _ll(a, b, c, d):
    """Log-likelihood (Rayson). a=freq target, b=freq ref, c=total target, d=total ref."""
    e1 = c * (a + b) / (c + d)
    e2 = d * (a + b) / (c + d)
    g = 0.0
    if a > 0:
        g += a * math.log(a / e1)
    if b > 0:
        g += b * math.log(b / e2)
    return 2 * g


def keyness(target_freq, target_total, ref_freq, ref_total,
            min_freq=3, content_only=True, top=40):
    """Devuelve las palabras clave del target frente a la referencia, ordenadas por log-likelihood."""
    rows = []
    for w, a in target_freq.items():
        if a < min_freq:
            continue
        if content_only and (w in STOPWORDS_EN or len(w) <= 2):
            continue
        b = ref_freq.get(w, 0)
        ll = _ll(a, b, target_total, ref_total)
        sign = "+" if (a / target_total) > (b / ref_total if ref_total else 0) else "-"
        rows.append({"word": w, "ll": round(ll, 2), "sign": sign,
                     "f_sub": a, "f_ref": b,
                     "per10k_sub": round(a / target_total * 10000, 1),
                     "per10k_ref": round(b / ref_total * 10000, 1) if ref_total else 0.0})
    rows.sort(key=lambda r: r["ll"], reverse=True)
    # solo sobrerrepresentadas (signo +), que son las "clave" del subcorpus
    rows = [r for r in rows if r["sign"] == "+"]
    return rows[:top] if top else rows


def collocations(segments, node, role="ST", window=5, min_coll_freq=3, top=25):
    """Colocaciones del nodo en los segmentos del rol indicado. Devuelve log-Dice y MI."""
    node = node.lower()
    f_word = collections.Counter(); total = 0
    f_coll = collections.Counter(); f_node = 0
    for s in segments:
        if s["role"] != role:
            continue
        toks = tokenize(s["text"]); total += len(toks); f_word.update(toks)
        idx = [i for i, t in enumerate(toks) if t == node]
        f_node += len(idx)
        for i in idx:
            lo = max(0, i - window); hi = min(len(toks), i + window + 1)
            for j in range(lo, hi):
                if j == i:
                    continue
                f_coll[toks[j]] += 1
    out = []
    for c, fc in f_coll.items():
        if fc < min_coll_freq or c == node:
            continue
        fw = f_word[c]
        log_dice = 14 + math.log2(2 * fc / (f_node + fw)) if (f_node + fw) else float("-inf")
        mi = math.log2(fc * total / (f_node * fw)) if (f_node and fw) else float("-inf")
        out.append({"collocate": c, "f_coll": fc, "f_total": fw,
                    "log_dice": round(log_dice, 2), "mi": round(mi, 2)})
    out.sort(key=lambda r: r["log_dice"], reverse=True)
    return out[:top] if top else out


def _aligned_segment(segments, src, target_role):
    """Devuelve el segmento del rol objetivo (mismo discurso) con mayor solape temporal."""
    if src["start"] is None:
        return None
    s0, s1 = src["start"], src["start"] + (src["duration"] or 0)
    best, best_ov = None, -1
    for s in segments:
        if s["speech_id"] != src["speech_id"] or s["role"] != target_role or s["start"] is None:
            continue
        t0, t1 = s["start"], s["start"] + (s["duration"] or 0)
        ov = min(s1, t1) - max(s0, t0)
        if ov > best_ov:
            best_ov, best = ov, s
    return best


def concordances(segments, node, role="ST", context=6, align=True, max_lines=40):
    """KWIC del nodo en el rol indicado, con el segmento alineado del otro rol si align=True."""
    node = node.lower(); other = "TT" if role == "ST" else "ST"
    lines = []
    for s in segments:
        if s["role"] != role:
            continue
        toks = s["text"].split()
        low = [t.lower().strip(".,;:()") for t in toks]
        for i, t in enumerate(low):
            if t == node:
                left = " ".join(toks[max(0, i - context):i])
                right = " ".join(toks[i + 1:i + 1 + context])
                rec = {"speech_id": s["speech_id"], "seg_index": s["seg_index"],
                       "left": left, "kwic": toks[i], "right": right}
                if align:
                    tt = _aligned_segment(segments, s, other)
                    rec["aligned"] = tt["text"] if tt else "(sin alinear)"
                lines.append(rec)
                if len(lines) >= max_lines:
                    return lines
    return lines


if __name__ == "__main__":
    SEG = "out/epic_scored_segmentos.csv"; REF = "out/epic_en_reference_freq.csv"
    segs = load_segments(SEG)
    tf, tt_total = freq_from_segments(segs, "ST")
    rf, rtotal = load_reference_freq(REF)
    print(f"Subcorpus EN: {tt_total} tokens | Referencia: {rtotal} tokens\n")
    print("=== PALABRAS CLAVE (keyness, top 20 de contenido) ===")
    print(f"{'palabra':16}{'LL':>9}{'f_sub':>7}{'f_ref':>7}{'/10k sub':>9}{'/10k ref':>9}")
    for r in keyness(tf, tt_total, rf, rtotal, top=20):
        print(f"{r['word']:16}{r['ll']:9.1f}{r['f_sub']:7}{r['f_ref']:7}{r['per10k_sub']:9.1f}{r['per10k_ref']:9.1f}")
    print("\n=== COLOCACIONES de 'rights' (top 12 por log-Dice) ===")
    for c in collocations(segs, "rights", top=12):
        print(f"  {c['collocate']:16} log-Dice={c['log_dice']:.2f}  MI={c['mi']:.2f}  (n={c['f_coll']})")
    print("\n=== CONCORDANCIAS de 'rights' (5 líneas, con interpretación alineada) ===")
    for ln in concordances(segs, "rights", max_lines=5):
        print(f"  [{ln['speech_id']}] ...{ln['left'][-40:]} [{ln['kwic']}] {ln['right'][:40]}...")
        print(f"      TT> {ln['aligned'][:90]}")
