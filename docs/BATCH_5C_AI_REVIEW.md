# Procedimiento 5C de revisión semántica por IA

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
Se conserva la procedencia `executor_fallback` frente a selección del LLM.

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
