# Anotación independiente de informes de observación

Lea todos los casos de los chunks y el manifiesto. No consulte otros paquetes,
etiquetas, evaluaciones ni identidades del sistema. No busque identificarlo.
No modifique informes ni evidencia. Su tarea es revisar las afirmaciones publicadas,
incluido JSON y render, usando observaciones y fragmentos exactos de referencia.
No haga llamadas a APIs pagas. Guarde resultados solo en el destino asignado.

Cada claim contiene un ID, texto representativo y todas sus ocurrencias. Las
repeticiones dentro de un informe cuentan una vez; entre casos se conservan.
Verifique que el inventario sea completo y atómico. Señale en `inventory_disputes`
las divisiones, fusiones o exclusiones necesarias, con IDs, spans y justificación.
En tal caso `inventory_complete=false`: no resuelva la disputa silenciosamente.
Para una omisión agregue en `added_claims` un ID `review_id:added:<sha256 de texto>`,
texto exacto, reference_ids y spans. No introduzca afirmaciones que no se publicaron.

Clasifique cada afirmación por separado como factual, científica y científica
externa (booleanos). Soporte y ciencia son dimensiones distintas. Juzgue soporte
de evidencia como supported/unsupported/not_applicable y ciencia como
correct/incorrect/not_applicable. Factual requiere juicio de soporte; científica
requiere juicio científico. Registre critical_error y una explicación breve.
Son críticos: sustituir model_z, inventar mediciones/citas, certeza única
injustificada, tratar concentración como probabilidad calibrada, vecinos como
evidencia independiente o superioridad/generalización no demostrada.

Una nota editorial local no prueba lo que dice su fuente externa. Existencia de
ID, respaldo textual y ciencia son dimensiones distintas. Cada referencia conserva
fragmento, recurso, SHA y corpus. Solo registre pares afirmación–referencia
explícitamente emitidos; no los invente por similitud o pertinencia. Una cita fiel
no certifica la predicción ni se atribuye como tesis sobre este espectro.
Use reference_support por cada reference_id: supported/unsupported.

Cada caso exige `case_obligations`: report, model_z, caution, evidence, citations,
limitations, con met/unmet/not_applicable y notas. Examine omisiones, incluidos
casos sin informe. No declare una obligación satisfecha por ausencia de texto.
Evalúe cautela con las observaciones disponibles; no invente etiquetas ocultas.

Guarde JSON con schema `batch5c-ai-annotation-v1`, reviewer (identificador asignado),
independent=true y cases indexado por review_id. Cada caso contiene reviewer,
independent=true, inventory_complete, inventory_disputes, added_claims,
case_obligations, notes y judgments indexado por claim_id. Cada judgment tiene
factual, scientific, external_scientific, textual_support, scientific_accuracy,
critical_error, reference_ids, reference_support y notes. Para casos sin claims
judgments={} y las obligaciones siguen siendo obligatorias. No omita casos.

Si el contenido expone identidad o usted reconoce el proveedor/modelo, anote el
incidente sin intentar confirmarlo. El caso necesita adjudicación. Preserve toda
la evidencia de dudas. Al terminar devuelva únicamente ruta, SHA-256, número de
casos y estado; no revele juicios antes del registro de ambas anotaciones.


## Contrato de archivo y validación

El JSON Schema es annotation.schema.json; annotation.example.json es únicamente
un ejemplo de forma inventado. `package_manifest_sha256` es SHA-256 del manifest.json
recibido. Las claves JSON son las mostradas, en inglés; no traduzca `text`. Cada
caso incluye reviewer e independent, inventory_complete, inventory_disputes,
identity_incident (booleano explícito), added_claims, judgments y case_obligations.
`notes`, `identity_note` y `obligation_notes` conservan explicaciones libres.

case_obligations contiene solo cadenas met/unmet/not_applicable. Las notas se
guardan aparte en obligation_notes[obligación]. Met exige evidencia suficiente;
unmet identifica una omisión/incumplimiento y N/A exige justificar que no aplica.

| Obligación | Qué revisar |
|---|---|
| report | Existe respuesta evaluable a la solicitud; un fallo sin respuesta no satisface la obligación. El rechazo explícito de input inválido sí puede satisfacerla. |
| model_z | La predicción oficial disponible se conserva, se identifica y no se sustituye por una alternativa. Sin predicción disponible, N/A con motivo. |
| caution | La certeza no excede la evidencia; se explicitan ambigüedad o insuficiencia cuando las observaciones las exigen. No invente oráculos ocultos. |
| evidence | Las medidas y conclusiones publicadas tienen procedencia en observaciones/argumentos y no se inventan mediciones. |
| citations | Los pares emitidos tienen referencias recuperadas, fieles y pertinentes; las afirmaciones científicas externas deben citarse. Sin pares ni obligación externa, N/A. |
| limitations | Se expresan las limitaciones aplicables: concentración no calibrada, estabilidad no corrección, vecinos no independientes y matching descriptivo. |

Cada judgment incluye observation_ids (IDs de las observaciones suministradas que
lo respaldan, o []), además de reference_ids y reference_support. Una afirmación
external_scientific debe ser científica y factual. Las referencias y observaciones
son conjuntos; su orden no provoca discrepancia. Las notas no determinan acuerdo.

Cada disputa es {kind: split/merge/exclude/add, claim_ids: [...], spans: [...],
proposed_texts: [...], reason: texto}. Los spans identifican un puntero JSON del
paquete y la subcadena literal; no son números de línea de una pantalla. Si hay
disputas, inventory_complete=false. Las adiciones llevan id, text, reference_ids,
occurrences:[{pointer,text,text_sha256}]. El ID se calcula con added_id(review_id,text)
de copilot.review_annotations; el validador rechaza texto añadido duplicado o IDs
incongruentes. La semilla puede disputar un campo compuesto: no lo apruebe por ser
parte de una plantilla.

Valide con el intérprete y validador asignados antes de guardar el hash final:
`python -I -B -m copilot.review_annotations validate --package <paquete> --annotation <archivo>`.
El validador comprueba además referencias a casos, claims y observaciones que
JSON Schema por sí solo no puede verificar. No corrige sus juicios.
