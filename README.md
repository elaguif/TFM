
ANEXO DE REPRODUCIBILIDAD
Trabajo de Fin de Máster
Autora: Elena Aguirre Fernández Bravo


Este paquete permite dos cosas: (a) regenerar todo el proceso desde el
corpus, paso a paso, y (b) explorar los resultados ya calculados en
unos minutos, sin descargas. El borrador del TFM se entrega por
separado.


---------------------------------------------------------------------
1. CONTENIDO DEL PAQUETE
---------------------------------------------------------------------

CUADERNOS (Jupyter / Google Colab)

  TFM_reproduccion_íntegra.ipynb
      Reproduce todo el proceso, desde la descarga del corpus hasta
      los resultados del análisis. Es autónomo: instala lo que
      necesita, escribe los scripts, ejecuta el pipeline completo y
      desarrolla el análisis (apartados 3.1 a 3.8).

  TFM_analisis.ipynb
      Versión ligera. Carga los CSV ya puntuados y ejecuta solo el
      análisis (los mismos apartados 3.1 a 3.8). No descarga el corpus
      ni instala modelos; corre en un par de minutos. Pensado para la
      exploración de los resultados.

SCRIPTS (Python 3)
Son idénticos a las celdas correspondientes del cuaderno íntegro; se
incluyen sueltos para poder leerlos y ejecutarlos fuera del cuaderno.

  epic_pipeline.py
      Prepara el subcorpus: empareja cada original con su
      interpretación, aplica los filtros de tema y longitud, limpia
      las convenciones de oralidad de EPIC y segmenta con las marcas
      de tiempo. Genera epic_en_es_segmentos.csv y
      epic_en_es_discursos.csv.

  nrc_scorer.py
      Puntuación léxica con los recursos NRC (EmoLex y VAD), en sus
      versiones bilingües: ocho emociones y polaridad, más valencia,
      activación (arousal) y dominancia. Lo usa epic_assemble.py.

  pysent_chunk.py
      Puntuación de sentimiento con pysentimiento (modelo neuronal
      preentrenado), en lotes reanudables. Genera pysent_cache.csv.

  epic_assemble.py
      Reúne la puntuación NRC (recalculada al vuelo) y la de
      pysentimiento (desde la caché) a nivel de segmento, y agrega por
      discurso con medias de ST, de TT y su diferencia (delta). Genera
      epic_scored_segmentos.csv y epic_scored_discursos.csv.

  epic_keywords.py
      Instrumentos de apoyo al análisis cualitativo: palabras clave
      (keyness por razón de verosimilitud), colocaciones (log-Dice e
      información mutua) y concordancias (KWIC con el segmento
      interpretado alineado por marcas de tiempo).

DATOS (CSV de salida)

  epic_en_es_segmentos.csv   (4.872 filas)
      Un segmento por fila, con su texto limpio y sus marcas de
      tiempo. Salida del pipeline.

  epic_en_es_discursos.csv   (71 filas)
      Metadatos por discurso (tema, fecha, orador, etc.).

  pysent_cache.csv           (4.872 filas)
      Puntuaciones de pysentimiento por segmento.

  epic_scored_segmentos.csv  (4.872 filas)
      Segmentos con todas las puntuaciones (NRC + pysentimiento). En
      90 segmentos la valencia aparece vacía: son segmentos sin
      ninguna palabra recogida en el léxico VAD, lo cual es esperado.

  epic_scored_discursos.csv  (71 filas)
      Medias por discurso para cada métrica, en ST, en TT y su delta.

  epic_en_reference_freq.csv
      Frecuencias de palabra del EPIC inglés completo (89.741 tokens),
      que sirven de referencia interna para el cálculo de keyness.

  README.txt
      Este archivo.

El subcorpus se organiza en dos estratos, conservados como variable de
análisis: Estrato I, acción exterior y conflicto (47 discursos), y
Estrato II, Consejo Europeo y orientación estratégica (24 discursos).


---------------------------------------------------------------------
2. CÓMO USARLO
---------------------------------------------------------------------

Las dos vías dan el mismo análisis. Se recomienda Google Colab.

VÍA A. Reproducción íntegra (TFM_reproduccion_íntegra.ipynb)

  Ejecutar las celdas en orden. El cuaderno, por sí mismo:
    1. instala pysentimiento;
    2. descarga el corpus EPIC v2.0;
    3. pide subir los dos léxicos NRC (véase el apartado 3);
    4. escribe los cinco scripts;
    5. ejecuta el pipeline, la puntuación y el ensamblado;
    6. construye la referencia de palabras clave;
    7. desarrolla el análisis (3.1 a 3.8).
  Al terminar, los seis CSV quedan en la carpeta out/.
  Conviene activar GPU para que pysentimiento sea ágil.

VÍA B. Análisis rápido (TFM_analisis.ipynb)

  No descarga nada ni reejecuta los modelos. Necesita en la carpeta de
  trabajo cuatro archivos de este paquete:
      epic_keywords.py
      epic_scored_segmentos.csv
      epic_scored_discursos.csv
      epic_en_reference_freq.csv
  La primera celda los recoge (en Colab los pide para subir) y coloca
  los CSV donde el resto del cuaderno los busca. A partir de ahí,
  reproduce el análisis sobre esos datos ya puntuados.


---------------------------------------------------------------------
3. RECURSOS EXTERNOS NECESARIOS (no incluidos)
---------------------------------------------------------------------

Solo hacen falta para la VÍA A. La VÍA B trabaja sobre los CSV ya
generados y no los necesita.

  Corpus EPIC v2.0
      Se descarga de Zenodo (https://zenodo.org/records/13856205). El
      cuaderno íntegro lo descarga de forma automática.

  Léxicos NRC (Saif M. Mohammad)
      NRC Emotion Lexicon (EmoLex) y NRC VAD Lexicon, en sus versiones
      con traducción al español (ficheros de la carpeta
      OneFilePerLanguage: Spanish-NRC-EmoLex.txt y
      Spanish-NRC-VAD-Lexicon.txt). Se obtienen en
      https://saifmohammad.com/WebPages/lexicons.html y se suben al
      cuaderno íntegro, que tiene una celda preparada para ello.
      Nota: se utiliza NRC-VAD v1, porque las versiones posteriores no
      incluyen traducción al español.

No se redistribuyen aquí por sus condiciones de uso y por tamaño.


---------------------------------------------------------------------
4. FLUJO DE DATOS (qué genera qué)
---------------------------------------------------------------------

  corpus EPIC
      -> epic_pipeline.py
         -> epic_en_es_segmentos.csv
            epic_en_es_discursos.csv

  epic_en_es_segmentos.csv
      -> pysent_chunk.py
         -> pysent_cache.csv

  epic_en_es_segmentos.csv + epic_en_es_discursos.csv
  + pysent_cache.csv + nrc_scorer.py
      -> epic_assemble.py
         -> epic_scored_segmentos.csv
            epic_scored_discursos.csv

  corpus EPIC (inglés completo)
      -> epic_en_reference_freq.csv

  epic_scored_segmentos.csv + epic_scored_discursos.csv
  + epic_en_reference_freq.csv + epic_keywords.py
      -> análisis (apartados 3.1 a 3.8)


---------------------------------------------------------------------
5. DEPENDENCIAS
---------------------------------------------------------------------

  - Python 3.
  - pysentimiento (solo VÍA A; arrastra transformers, torch y otras).
  - pandas, numpy, scipy y matplotlib, para el análisis. En Colab
    vienen preinstaladas.
  - epic_pipeline.py, nrc_scorer.py, epic_assemble.py y
    epic_keywords.py usan solo la biblioteca estándar de Python.


---------------------------------------------------------------------
6. NOTA SOBRE LA REPRODUCIBILIDAD
---------------------------------------------------------------------

  - La puntuación NRC es determinista: devuelve siempre los mismos
    valores, y los scripts producen CSV idénticos en reejecuciones
    equivalentes.
  - La puntuación con pysentimiento depende del modelo preentrenado
    que se descargue; un cambio de versión del modelo puede alterar
    ligeramente los valores. Los CSV incluidos corresponden a la
    ejecución de referencia descrita en el TFM. Para dejar constancia
    de la versión, puede anotarse la salida de: pip show pysentimiento.
  - Todos los scripts usan rutas relativas respecto a la carpeta de
    trabajo y escriben en out/.

=====================================================================
