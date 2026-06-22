# -*- coding: utf-8 -*-
"""
Scorer basado en los léxicos NRC (Mohammad), para inglés y español.

Usa dos recursos, en sus versiones bilingües (un mismo fichero contiene la
palabra inglesa, sus puntuaciones y la traducción española, de modo que ambas
lenguas se miden con entradas y puntuaciones idénticas: máxima comparabilidad):

  - NRC EmoLex  -> 8 emociones (Plutchik) + polaridad positiva/negativa
  - NRC-VAD     -> valencia, activación (arousal) y dominancia [0-1]

Devuelve, por segmento:
  - polarity        : (#pos - #neg) / (#pos + #neg)  en [-1, 1]   (EmoLex)
  - valence/arousal/dominance : medias VAD de las palabras reconocidas
  - emo_<emoción>   : proporción de tokens asociados a cada emoción
  - coverage        : nº de tokens y nº reconocidos en cada léxico
"""
import os, re

NRC_DIR = "nrc"
EMOLEX_ES = os.path.join(NRC_DIR, "emolex/NRC-Emotion-Lexicon/OneFilePerLanguage/Spanish-NRC-EmoLex.txt")
VAD_ES    = os.path.join(NRC_DIR, "vad/NRC-VAD-Lexicon/OneFilePerLanguage/Spanish-NRC-VAD-Lexicon.txt")

EMOTIONS = ["anger","anticipation","disgust","fear","joy","sadness","surprise","trust"]
TOKEN_RE = re.compile(r"[a-záéíóúüñ]+", re.IGNORECASE)


def _load_emolex():
    """English y Spanish word -> dict de emociones/polaridad, desde el fichero bilingüe."""
    en, es = {}, {}
    with open(EMOLEX_ES, encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        # cols: English Word, anger, anticipation, disgust, fear, joy, negative,
        #       positive, sadness, surprise, trust, Spanish Word
        idx = {h: i for i, h in enumerate(header)}
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < len(header):
                continue
            rec = {k: int(p[idx[k]]) for k in
                   EMOTIONS + ["positive", "negative"]}
            enw = p[idx["English Word"]].strip().lower()
            esw = p[idx["Spanish Word"]].strip().lower()
            if enw:
                en[enw] = rec
            if esw:
                es[esw] = rec
    return en, es


def _load_vad():
    """English y Spanish word -> (valence, arousal, dominance), desde el fichero bilingüe."""
    en, es = {}, {}
    with open(VAD_ES, encoding="utf-8") as f:
        f.readline()  # cabecera: English Word, Valence, Arousal, Dominance, Spanish Word
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 5:
                continue
            try:
                v, a, d = float(p[1]), float(p[2]), float(p[3])
            except ValueError:
                continue
            enw, esw = p[0].strip().lower(), p[4].strip().lower()
            if enw:
                en[enw] = (v, a, d)
            if esw:
                es[esw] = (v, a, d)
    return en, es


class NRCScorer:
    _EMO = None
    _VAD = None

    def __init__(self, lang):
        assert lang in ("en", "es")
        self.lang = lang
        if NRCScorer._EMO is None:
            NRCScorer._EMO = _load_emolex()
            NRCScorer._VAD = _load_vad()
        self.emo = NRCScorer._EMO[0 if lang == "en" else 1]
        self.vad = NRCScorer._VAD[0 if lang == "en" else 1]

    def score(self, text):
        toks = TOKEN_RE.findall(text.lower())
        n = len(toks)
        out = {"n_tokens": n, "n_emolex": 0, "n_vad": 0,
               "polarity": 0.0, "valence": None, "arousal": None, "dominance": None}
        for e in EMOTIONS:
            out["emo_" + e] = 0.0
        if n == 0:
            return out
        pos = neg = 0
        emo_counts = {e: 0 for e in EMOTIONS}
        vs = []; ars = []; ds = []
        for w in toks:
            r = self.emo.get(w)
            if r is not None:
                out["n_emolex"] += 1
                pos += r["positive"]; neg += r["negative"]
                for e in EMOTIONS:
                    emo_counts[e] += r[e]
            vad = self.vad.get(w)
            if vad is not None:
                out["n_vad"] += 1
                vs.append(vad[0]); ars.append(vad[1]); ds.append(vad[2])
        out["polarity"] = (pos - neg) / (pos + neg) if (pos + neg) else 0.0
        for e in EMOTIONS:
            out["emo_" + e] = round(emo_counts[e] / n, 4)
        if vs:
            out["valence"] = round(sum(vs) / len(vs), 4)
            out["arousal"] = round(sum(ars) / len(ars), 4)
            out["dominance"] = round(sum(ds) / len(ds), 4)
        return out


if __name__ == "__main__":
    import epic_pipeline as P
    print("Cargando léxicos NRC...")
    sc = {"en": NRCScorer("en"), "es": NRCScorer("es")}
    print("EmoLex EN:", len(sc['en'].emo), "| ES:", len(sc['es'].emo),
          "| VAD EN:", len(sc['en'].vad), "| ES:", len(sc['es'].vad))
    tests = [
        ("en", "this is a dangerous and unacceptable threat to peace and security"),
        ("es", "esto es una amenaza peligrosa e inaceptable para la paz y la seguridad"),
        ("en", "I warmly welcome this excellent and hopeful agreement"),
        ("es", "acojo con satisfacción este acuerdo excelente y esperanzador"),
    ]
    for lang, t in tests:
        r = sc[lang].score(t)
        print(f"\n[{lang}] {t}")
        print(f"   polaridad={r['polarity']:+.2f} valencia={r['valence']} "
              f"arousal={r['arousal']} | cobertura EmoLex {r['n_emolex']}/{r['n_tokens']} "
              f"VAD {r['n_vad']}/{r['n_tokens']}")
        top = sorted(((r['emo_'+e], e) for e in EMOTIONS), reverse=True)[:3]
        print("   emociones top:", ", ".join(f"{e}={v}" for v, e in top if v > 0))
