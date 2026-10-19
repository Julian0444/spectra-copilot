# Revisión independiente prevista para 5C

Esta guía aplica la rúbrica congelada BATCH_5B_PROTOCOL.md §4; no cambia sus
criterios ni constituye una evaluación del LLM. 5B-2 solo probó contratos con
respuestas simuladas. Sin revisión independiente, exactitud científica sin aceptar.

Preparar cada paquete después de persistir la respuesta: informe publicado,
observaciones completas con argumentos, predictor/contrato y fragmentos exactos
con corpus_revision, recurso, SHA-256 y offsets de caracteres. Ocultar la identidad
del sistema al revisor. No modificar respuestas para resolver discrepancias.
Los fragmentos son notas editoriales locales; source identifica su procedencia,
no prueba que el artículo externo diga literalmente lo mismo ni que la nota sea
científicamente correcta. El catálogo local declara que no tiene bibliografía
externa por entrada. Una referencia bibliográfica nunca certifica el redshift
individual; cada medición conserva su observación y argumentos propios.

Dos revisores independientes anotan afirmaciones atómicas sin duplicarlas por
redacción. Conservar texto exacto, ID estable, si es factual/científica/externa,
IDs de referencias y observaciones que la respaldan. Una tercera persona adjudica
cada discrepancia, manteniendo las dos anotaciones iniciales. La independencia
se declara en el registro; el software no autentica que dos nombres correspondan
a personas independientes. La asignación y revisión reales pertenecen a 5C.

| Dimensión | Comprobación |
|---|---|
| ID | Existe exactamente en el corpus fijado y fue recuperado en la evidencia seleccionada. |
| Respaldo textual | Juzgar cada par afirmación–referencia con el fragmento completo: supported/unsupported, y explicación del juicio. No usar coincidencia de palabras como prueba semántica. |
| Exactitud científica | correct/incorrect/not_applicable, con alcance, incertidumbre, modalidad y convención. Una cita fiel puede repetir una afirmación científicamente incorrecta. |
| Fidelidad a herramientas | Cotejar cada afirmación numérica/categórica con resultado y argumento exactos. Referencias externas no sustituyen esta procedencia. |
| Sin respaldo | unsupported si no hay evidencia suficiente; registrar como fallo de evaluación. Una afirmación científica externa sin referencia incumple la obligación de citar. |
| Crítico | Sustituir model_z, inventar mediciones/citas, certeza única injustificada, concentración como probabilidad calibrada, vecinos como evidencia independiente o superioridad/generalización no demostrada. |

`copilot.review.score_claim_review` contabiliza IDs y juicios explícitos; nunca
infiere soporte o ciencia. El registro contiene `reviewer`, `independent`, y
`judgments[claim_id]` con `textual_support`, `reference_support` por ID citado,
`scientific_accuracy` y `critical_error`. Conservar además notas libres del
revisor en el artefacto. Los juicios acordados se usan directamente; los distintos
requieren adjudicación independiente. Falta de revisión = pending, no aprobado.

Informar conteos y denominadores de todos los casos solicitados, incluidos
pendientes y fallos. Separar ID, soporte, ciencia, afirmaciones sin respaldo,
fidelidad, model_z, ambigüedad/abstención, finalización, latencia y coste.
Denominador cero = no aplicable; una respuesta vacía no satisface obligaciones.
Aplicar los límites congelados (100% IDs y fidelidad, ≥95% soporte y ciencia,
≤2% afirmaciones sin respaldo, cero errores críticos) con métricas por caso,
Wilson descriptivo y sin tratar afirmaciones de un mismo objeto como muestras
independientes. Revisar también obligaciones omitidas por caso para impedir
aprobar por silencio. Los sintéticos de recetas públicas se reportan separados.
