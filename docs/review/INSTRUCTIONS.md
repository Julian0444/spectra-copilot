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
