# Procedimiento 5C de revisión semántica por IA

**Estado del cierre de 2026-10-27: correcciones en verificación.** Los dos P2
de D-r2 se corrigen bajo la nueva autorización; no se atribuye aún aprobación
independiente. El uso real exige registro 5C-2 y revisión sin P1/P2.
Véase [estado](BATCH_5C_REMAINING.md).

Este procedimiento implementa la rúbrica congelada de BATCH_5B_PROTOCOL.md §4.
Todavía no constituye la adenda 5C-2 ni habilita aceptación. Esa adenda registrará
la variante elegida y la identidad instalada final después del piloto.

Dos sesiones nuevas, GPT-6 Astra y Claude Opus 5.5, distintas del coordinador y
del revisor de implementación, reciben paquetes idénticos. Es revisión por IA,
no revisión humana independiente. Opus y el LLM evaluado, Haiku, comparten
proveedor. Se registran modelo y opciones seleccionados y los límites de su
verificación efectiva. Solo coordinador y dos anotadores estarán activos.
No se permiten llamadas pagas de la aplicación durante la anotación.

## Ceguera y registro

`copilot.review_packet` verifica sello y registro externo antes de leer outputs.
No recibe etiquetas. Incluye los 128 casos, incluso fallos y pendientes, en
orden determinista; divide por tamaño sin seleccionar resultados favorables.
Se hashean instrucciones, manifiesto, inventario, código de segmentación y cada
archivo antes de entregar copias equivalentes. El mapa review_id→alias permanece
fuera de ambos paquetes y las identidades de ejecución tampoco se entregan.

Superficie evaluada: JSON publicado (estado, model_z, predictor, contrato,
alternativas, explicación, citas, limitaciones y violaciones) y render exacto.
Observaciones, argumentos y predicción acompañan como evidencia. Se excluyen
presupuesto, costes, tiempos, modelo del LLM, historia y thinking. Predictor y
contrato publicados se conservan íntegros, incluidos rangos, fórmulas y hashes.
**No se sustituye la identidad del predictor ni se modifica texto científico.**
Se conserva `llm_selected` o `undetermined_after_failure`, según el estado y
las violaciones registradas; un fallo no demuestra selección del LLM ni fallback.

Se buscan nombres de proveedor/modelo, IDs de API, aliases exactos y rutas
locales en lo entregado. Cualquier acierto se declara como incidente de ceguera;
el texto permanece íntegro. Si las notas de un anotador nombran al proveedor o
modelo evaluado, también se declara. Los acuerdos de casos afectados requieren
adjudicación de Julian; no se aceptan directamente.

Cada sesión guarda su anotación privada y devuelve solo estado, ruta y hash.
El coordinador registra ambos hashes antes de leer cualquiera de las dos o
mostrar el trabajo de un anotador al otro. Una caída conserva lo producido;
no se inventa una segunda anotación. Lo incompleto queda pendiente.

## Inventario y denominadores

**Las afirmaciones equivalentes dentro de un informe se agrupan en un único ID,
con todos sus spans y hashes de texto; no se duplican por redacción.** Grupos
prerregistrados: model_z del encabezado y predictor; concentración no calibrada;
estabilidad no implica corrección; vecinos no independientes; matching descriptivo.
Ausencia de soporte no refuta y matching no confirma físicamente son átomos
separados. Medidas, alternativas y citas conservan sus ubicaciones exactas.
No hay agrupación entre casos: la métrica primaria conserva sus ocurrencias.
La sensibilidad sin invariantes, repetición y tasas por caso se informan aparte.

El inventario automático es una propuesta que ambos anotadores revisan: pueden
disputar omisiones, segmentación o equivalencias. Ninguna marca del coordinador
determina C_sci o C_fact. Cada anotador clasifica factual/científica/externa y
juzga soporte, ciencia, citas y criticidad. Disputas de inventario y pertenencia
a denominadores van a Julian junto con las anotaciones originales. Se presentan
recuentos iniciales, de cada anotador, acordados y finales. Los conteos inclusivos
provisionales del scorer son diagnósticos pendientes, nunca el denominador final.

C_pair incluye únicamente pares afirmación–cita emitidos: no se inventan por
pertinencia y una cita literal no se convierte en tesis sobre el espectro.
El extracto `quotation:<id>`, su encabezado y `Retrieved reference IDs` no crean
pares. La extracción es factual, no científica/externa, con ciencia N/A; soporte
se juzga contra el fragmento recuperado. No exige una autocita. Referencias de
juicios iguales a las semillas salvo disputa registrada y limitadas a las citas
del caso. El contrato entregado contiene la regla completa y su validación.
Denominador cero es N/A, nunca 100%. Si C_pair=0 y no hay obligación externa
omitida, la aceptación global queda pendiente de criterio explícito de Julian.
Sin adjudicar desacuerdos, exactitud científica y aceptación global pendientes.

Cada caso exige anotación de informe, model_z, cautela, evidencia, citas y
limitaciones, incluso sin afirmaciones. El silencio no satisface obligaciones.
El resultado mecánico es autoritativo para lo que comprueba; un hallazgo semántico
contradictorio es otro canal y va a Julian. Fallos y críticos se unen por caso sin
doble conteo. Los anotadores no ven puntuaciones mecánicas ni etiquetas.

## Artefactos y cierre

Instrucciones entregadas: `review/INSTRUCTIONS.md`. Juicios categóricos se comparan
sin notas libres; notas se preservan para adjudicación. `score_annotation_pair`
contabiliza clasificaciones y omisiones independientes. Los scores se escriben
fuera del directorio sellado, en rutas nuevas que no se sobrescriben.
N=128 global, 80 reales y 48 sintéticos; se presentan M, C_id, C_pair, C_sci,
C_fact y A conforme al protocolo, estratos y Wilson por caso. Las recetas públicas
son comprobaciones de mecanismo. Una nueva sesión de Opus revisa agregados,
denominadores, sello, identidad, costes y fidelidad del informe sin repetir pagos.


## Unión validada y adjudicación de inventario

El coordinador registra first_sha256 y second_sha256 en un archivo exclusivo
`batch5c-annotation-registration-v1` con registered_before_reading_judgments=true
antes de leer contenido. Esta declaración se contrasta con el registro temporal
de herramientas; el software no puede demostrar por sí solo que nadie leyó antes.
Se auditan ambos hilos. Los paquetes se copian en directorios privados aleatorios;
se declara ceguera parcial sobre real/sintético porque el contenido puede revelarlo.
Etiquetas y puntuación mecánica de aceptación se abren solo después de registrar
ambos hashes; esto no impide puntuar desarrollo para la puerta del piloto.

`copilot.review_annotations join --package ... --mapping ... --first ...
--second ... --registration ... --output ... [--adjudication ...]` verifica los
hashes, manifiesto, sello, mapa, cobertura de todos los casos y ambos contratos.
Produce `batch5c-ai-reviews-v1`, indexado por alias, con bundles
`batch5c-ai-case-review-v1`. El scorer rechaza esquemas desconocidos; en propuesta
solo admite esa unión validada. La unión no lee etiquetas ni modifica anotaciones.

Adjudicación: archivo `batch5c-ai-adjudication-v1` con reviewer=Julian,
independent=true, package_manifest_sha256 y cases (solo los casos adjudicados).
Cada caso incluye reviewer, independent, judgments y case_obligations (solo las
disputadas salvo exposición de identidad, que requiere todas). Para inventario,
inventory_resolution contiene input_sha256=inventory_digest(semillas,primera,segunda),
claims (inventario final completo) y reason. Puede rechazar adiciones, excluir,
dividir o fusionar semillas únicamente sobre disputas/adiciones registradas.
Toda semilla y toda adición conjunta no disputada conserva ID, texto y
reference_ids. El adjudicador no usa added_claims. Un texto nuevo o reescrito
en la resolución debe proceder de proposed_texts o de adiciones registradas. Sin disputas ni adiciones se
rechaza una resolución. Cada fila registra inventory_changes: excluded, changed
y added; los cambios de reference_ids también cuentan como changed. Estos
conteos, forced y changed se agregan globalmente y por estrato. Los claims resultantes llevan texto exacto y spans;
los nuevos o modificados requieren juicio humano. Una resolución con hash viejo
se rechaza; una anotación independiente faltante siempre queda pendiente. Se
conservan conteos de semilla, cada anotador y final, además de los originales.

Las omisiones y pendientes se agregan por obligación. Las tasas semánticas por
caso y Wilson son descriptivas (casos enteramente correctos/respaldados); no
reemplazan los umbrales agrupados de afirmaciones. Las notas que revelen identidad
y blindness_intact=false fuerzan juicio humano en todo el caso.

Los desacuerdos iniciales se conservan en disagreements; forced y changed
separan los juicios exigidos por pérdida de ceguera o cambios de inventario.
El score registra reviews_sha256; cada caso de propuesta exige el esquema IA.
El score no vuelve a reconstruir la unión: se conserva la unión validada y su
registro, paquete y mapa para comprobar su procedencia con el hash registrado.

Herramientas sin etiquetas:
`python -I -B -m copilot.review_annotations worksheet --package <paquete>
--first <primera> --second <segunda> --registration <registro> --output <hoja>`
calcula los input_sha256 y lista disputas, inventarios originales y pendientes.
claims contiene el catálogo completo: semillas y adiciones; claim_origins distingue
seed, joint_addition, first_addition y second_addition. No se construye un inventario
final a partir de las semillas solas.
No necesita mapa privado ni etiquetas. Para validar una adjudicación:
`python -I -B -m copilot.review_annotations validate --package <paquete>
--adjudication <archivo> --first <primera> --second <segunda> --registration <registro>`.
La validación acepta juicios humanos de adiciones registradas de un solo anotador,
sin obligar a una resolución si no cambia el inventario.

## Límites declarados tras revisión previa R1

La clasificación factual de los extractos quotation puede diluir la fracción de
afirmaciones sin respaldo. Se conservará la métrica preregistrada y se publicará
aparte una sensibilidad descriptiva de C_fact excluyendo extractos, sin nuevo
umbral ni cambio de aceptación. Un inventario marcado incompleto puede omitir
juicios: el validador no los rellena y el caso permanece pendiente de adjudicación.
Las adiciones no pueden duplicar el texto exacto de ninguna semilla.
