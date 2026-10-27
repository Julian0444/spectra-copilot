# Lote 5C — mecánica aprobada, adjudicación pendiente (2026-10-27)

La repetición del piloto eligió low y pasó la puerta operativa (11/11 válidos).
Las correcciones D-P2-N1/N2 y P3-N1/N2/N3 fueron verificadas en dos rondas nuevas
de Opus 5.5. R1 encontró un P2 residual de inventario; rojo 78a1d8b (11 fallos)
→ verde 0074cbc, con 425 pruebas instaladas. R2 concluyó **0 P1 y 0 P2**.
La adenda 5C-2, procedimiento corregido e identidad quedaron registrados antes
de materializar. Build-02 conserva el camino LLM del piloto ejecutado; no se
repitió ni modificó el piloto aprobado.

## Ejecución única de aceptación

Instalación evaluada: FM e15d3a9 y Copilot 0074cbc, build-02/acceptance-env,
variante low, techo US$12,80. Custodio offline, vistas separadas y comprobador
previo: 5.398 superficies, cero hallazgos, incluidos los 128 NPZ y el plan.
El sello y su registro externo se escribieron antes de leer cualquier etiqueta.

- Solicitados e intentados: **128/128** (población congelada: 80 reales, 48 sintéticos).
- Estados de ejecución: 72 ambiguous, 49 insufficient_data, 6 invalid_input,
  1 explanation_incomplete; 0 pending, timeout, technical_error, max_tokens o refusal.
- **126 llamadas, cero reintentos**, un único intento por caso.
- Coste certificado: **US$0,1086672**, media por solicitado **US$0,0008489625**.
- Latencia total: p50 5,400725 s; p95 6,851419 s; máximo 8,769263 s.

Estos datos describen la ejecución; la puntuación posterior figura debajo.
La explicación incompleta se conserva y no se repite. Las 128 filas permanecen
en todos los denominadores globales aplicables; no se elimina ningún fallo.
Sello: `6131d5544efd5b56b67f536436b09a1403d6709d7bdc5915c5673a5cc7adcd72`.
Identidad evaluada: `a1415a165bf05ace0b8924853af900926b358d4b8b5bab3d804134153b0c57b8`.
El registro canónico y las trazas se conservan en el estado privado.
[Derivado público de ejecución](evidence/batch5c-acceptance-execution-public.json):
879.977 tokens de entrada, 41.339 de salida; 126 reservas y 126 liquidaciones
recalculadas, ninguna reserva pendiente. Los 128 casos usaron workers nuevos;
el primero tardó 6,210453 s y permanece en la latencia total.

## Puntuación mecánica y anotación IA terminadas

La puntuación se realizó después de registrar ambos hashes y verificar el sello
externo antes de abrir las etiquetas. **Pasan las comprobaciones mecánicas** del
protocolo; esto no aprueba exactitud científica ni aceptación global.

| Comprobación | Global | Reales | Sintéticos |
|---|---:|---:|---:|
| Completados / solicitados | 127/128 | 79/80 | 48/48 |
| model_z conservado / elegibles | 122/122 | 80/80 | 42/42 |
| Unidades de evidencia fieles | 909/909 | 621/621 | 288/288 |
| Casos válidos fieles a herramientas | 122/122 | 80/80 | 42/42 |
| Abstenciones requeridas | 18/18 | N/A (0/0) | 18/18 |
| Menciones de IDs de cita válidas | 3/3 | 3/3 | N/A (0/0) |

La cobertura de predicción es 122/122 entradas elegibles, **122/128 solicitados**;
los seis rechazos inválidos siguen en N. La explicación incompleta cuenta como
fallo de completitud. El p95 global y por estrato queda bajo 60 s; el coste
certificado queda bajo US$12,80 y la media bajo US$0,10. Fuentes, intervalos y
estratos completos: [derivado público de puntuación](evidence/batch5c-acceptance-score-public.json).
Las tres menciones válidas son pertenencia de ID, no pares científicos.

Dos sesiones nuevas, GPT-6 Astra y Claude Opus 5.5, recibieron copias equivalentes
de un paquete ciego de 128 casos y 2.191 semillas. Los dos archivos se guardaron
y registraron por hash antes de que el coordinador abriera cualquiera de sus
juicios o las etiquetas. Los revisores previos estaban cerrados. La unión validó.
Es **revisión por IA**, no revisión humana; Opus y Haiku comparten proveedor.
Cada anotador construyó sus juicios por afirmación con scripts propios después
de leer los casos. Ese método no equivale a validación humana independiente.

- Unión provisional: 2.194 afirmaciones, incluidas tres adiciones de Astra y cero
  de Opus; 894 afirmaciones inicialmente en desacuerdo y pendientes.
- Inventario pendiente: 122 casos; revisión semántica pendiente: **128/128**.
- Disputas de inventario declaradas: 1.198 por Astra y 197 por Opus (recuentos por
  anotador, no una suma de disputas únicas). Nueve casos discrepan en obligaciones.
- Ciencia: 783 juicios acordados correctos sobre denominador provisional 1.673;
  sin soporte: 6 sobre denominador provisional 2.194. **Ambas tasas son null**,
  no 46,8% de exactitud ni un aprobado del umbral de afirmaciones sin soporte.
- C_pair=0/0 ⇒ N/A y aceptación global pendiente. Seis obligaciones de evidencia
  acordadas como incumplidas se conservan; obligaciones pendientes: cautela 7,
  evidencia 3 y limitaciones 6. Cero indicadores críticos acordados no demuestra
  ausencia de errores críticos mientras la revisión siga pendiente.
- Sin adjudicación humana: forced=0, changed=0, inventory_changes=0. Sensibilidad
  descriptiva sin tres extractos: 6/2.191, tasa null; no altera el criterio.

El paquete privado de adjudicación contiene los 128 casos, catálogo completo,
textos y spans, ambos juicios, todas las disputas, contexto mecánico y campos
humanos vacíos: 84 archivos, 75.251.019 bytes. Manifiesto SHA-256:
`93da1dcb66ef81be9cd80343ec42aa94d1b8f49275e7b91ae0a075b86874d137`.
No se adjudicó ninguna diferencia ni se puntuó la plantilla vacía.

Límites de procedimiento declarados: orden de custodia conservado y ceguera
real/sintética parcial; identidades de sesión declaradas por la orquestación.
Opus escribió progreso con contenido en su sesión aislada, contra la instrucción
de comunicar solo recuentos. El coordinador leyó esa conversación después del
registro de ambos hashes; no se observó exposición del otro anotador. Se conserva
el rastro y no se repiten anotaciones. Los límites P3 del validador permanecen en
[REMAINING](BATCH_5C_REMAINING.md) y en las instrucciones a Julian.

Exactitud científica y aceptación global quedan pendientes de adjudicación humana
y de los límites del protocolo que sigan aplicando. **Publicación detenida hasta
PUBLICAR**. La R1 final de Opus reprodujo los resultados y encontró un P2 de
publicación: un README del Space puede reconstruir el servicio y resolver la
dependencia FM sin fijar. La respuesta corrige las afirmaciones sobre runtime,
exige aceptación expresa de ese efecto y añade comprobaciones posteriores.
El dictamen final del delta y los hashes de release se entregan con las notas
de release, sin atribuir aceptación a otro código ni repetir la evaluación.

El registro siguiente describe exclusivamente el cierre económico anterior.
Se conserva su cronología; su alcance fue sustituido por la autorización del
2026-10-27. Los resultados, costes y sellos anteriores no se modifican.

## Registro del cierre económico anterior


La repetición autorizada terminó y quedó sellada: **la variante elegida es
low, y pasa la puerta operativa**. No se abrió aceptación.
La única reconstrucción final se completó: build-08/final-env. La única
verificación final de Opus terminó: **bloqueado para abrir aceptación,
0 P1 y 2 P2 preexistentes de D**. No encontró P1/P2 nuevos en el cierre económico.
La puerta completa requiere además ausencia de P1/P2; los dos de D siguen declarados. Exactitud científica y aceptación global quedan pendientes.

## Piloto repetido: puntuación mecánica

Mismos 12 casos de desarrollo (4 reales y 8 sintéticos), variantes low/medium,
11 inputs válidos y uno inválido por variante. Misma selección, prompt, límites,
tarifas y regla prerregistrada; sin usar exactitud de z para elegir. Las 24 filas
se conservaron en el denominador. Sello externo verificado antes de etiquetas
de desarrollo. Fuente canónica: [resumen mecánico](evidence/batch5c-repeat.json);
filas y trazas privadas en pilot-repeat-run y pilot-repeat-mechanical.json.

| Variante | Solicitados | Informes con obligaciones | Explicación incompleta | max_tokens/refusal | Llamadas | US$ certificado |
|---|---:|---:|---:|---:|---:|---:|
| low | 12 | 11/11 | 0 | 0 | 11 | 0.0099734 |
| medium | 12 | 6/11 | 5 | 0 | 18 | 0.018088 |

Elección: más informes válidos con todas las obligaciones; empate → menos
max_tokens/refusal; empate → menor coste certificado; empate → low. Elegir una
variante no prueba que pase la puerta. Comprobaciones que no pasan:

- **low**: ninguna.
- **medium**: valid_reports, no_other_failures.

Se preservan model_z, IDs, cautela mínima, abstención esperada, rechazo inválido,
tokens/cotas, stop_reason, latencia y coste por fila en la puntuación privada.
No se cambia el prompt ni la rúbrica para corregir el resultado. No hay otro
piloto. La reconstrucción conservó el camino LLM y no requirió confirmación. No se anotaron afirmaciones semánticas por IA: Julian
lo dejó para otra sesión. Los 128 casos de aceptación (80 reales/48 sintéticos)
no se abrieron, materializaron, ejecutaron ni puntuaron.

## Intento original, credencial y presupuesto

El intento anterior se conserva como **«piloto interrumpido por fallo de
integración en la primera llamada, sin evidencia de comportamiento»**. Haiku
no produjo respuesta: low 1/12 intentado, medium 0/12, 23 pendientes. Fuente
[primer intento](evidence/batch5c-pilot.json); outputs y sellos originales intactos.
Su uso real sigue sin certificar; US$0 conocido no significa gasto total cero.

Una consulta gratuita posterior dio 401/AuthenticationError/authentication_error,
con request-id privado. Julian identificó **«credencial inválida; clave
reemplazada por Julian»**, guardada en Llavero anthropic-api-key a las 21:14 según
su declaración. La consulta gratuita única con clave nueva dio 200 y 4.805 tokens.
No se hizo generación diagnóstica. Se reconstruyó la entrada del primer caso
con sus observaciones, prompt y schemas; difiere la ruta temporal opaca que no
se había conservado. No se afirma igualdad byte a byte del request histórico.
El antiguo estado «no rotada» se conserva solo como historia anterior al reemplazo;
no se infiere vencimiento de la clave nueva. Ningún secreto se guardó en evidencias.

Presupuesto del piloto US$2,40. Reserva original debitada como gastada por orden
de Julian: US$0,0035706. Cap efectivo de la repetición: US$2,3964294.
Repetición: **US$0.0280614 certificado**, 29 llamadas, cero retries.
Contabilidad conjunta (repetición + reserva debitada): **US$0.031632**;
saldo sin gastar **US$2.368368**. Esa suma contable no certifica la factura
original. Consultas gratuitas: 2 total (401 y 200), generación diagnóstica: 0.
Confirmación: 0; aceptación: 0. No se transfiere saldo entre fases ni se reutiliza
el directorio original. Auditorías privadas separadas campaign y campaign-repeat.

## Implementado e instalado

A incorporó bootstrap predict+identify (2/6 análisis), esfuerzo low/medium
registrado, piloto limitado al manifiesto de desarrollo, presupuesto entero,
guardas de worker, campaña, identidad instalada y registro durable de llamadas.
B verificó wheels 0.3.0 nuevos, CLI/API, cinco herramientas MCP, recursos y Gradio.
FM v2.1 sigue predeterminado; CNN-17 experimental. No entrenamiento, splits,
selección de checkpoints ni inferencia sobre batch4a-v1/test.

El diagnóstico SDK registra tipo de excepción, HTTP, request-id y tipo de error
del proveedor, sin mensajes/cuerpos/secretos. Rojo a3f4bcc → verde 42b8f3c:
59 pruebas dirigidas pasan; 13 también desde instalación nueva. 400/401/403/429,
500/503/504/529 y timeout simulados. Dos expectativas SDK 503/504 incorrectas de
la primera preparación verde se corrigieron; los logs se conservaron.

Instalaciones preservadas y distintas:

- build-05/installed-env: primer intento interrumpido.
- build-06/release-env: entrega anterior, cuatro módulos de revisión/puntuación
  posteriores, demo comprobada sin API; D bloqueado con dos P2.
- **build-07/diagnostic-env**: diagnóstico y piloto repetido. Fuentes CP 7a260de,
  FM e5ae6cf; misma versión 0.3.0, hashes de wheels distintos. Se verificaron 22
  módulos Python por paquete, RECORD 45/29 archivos y ausencia de bytecode local.
  Único módulo adicional cambiado frente a build-06: copilot/budget.py.

[Manifiesto actual](evidence/batch5c-delivery.json), [guía](BATCH_5C_REPRODUCE.md).
La repetición usa protocolo CP 020ff39 congelado, adenda 5C-1c, identidades completas
privadas en repeat-registration. El saldo menor se impone en execute_plan y
manifest; el cap nominal de fase histórico permanece US$2,40. Ninguna instalación
se reinstaló durante el piloto. La reconstrucción final única build-08/final-env conserva todas las fuentes
ejecutables y llm_path de low por hash frente al build-07 evaluado. No requiere
confirmación. Fuentes CP 94a8f44 / FM 8514aab; RECORD e identidad verificados.
Evidencia en [verificación final](evidence/batch5c-final-verification.json).

## Revisiones y límites

Astra fue el único escritor; runtime declaró xhigh en etapas previas y high en
el cierre económico. Opus 5.5 revisó clones propios, sin clave ni llamadas pagas;
effort xhigh/fastMode=false solicitados, sin atestación del routing del proveedor.
A quedó aprobado tras dos rondas y una verificación puntual extra autorizada;
B aprobado en dos rondas. Se cerraron financiación insuficiente, fixture del
worker, rutas relativas, proyección llm_path y protocolo mutable.

D-r1 encontró 1 P1/3 P2, corregidos y verificados en R2. D-r2 dejó 2 P2: adjudicación
puede borrar acuerdos y referencias de extractos ambiguas. Reproducidos contra
build-06, siguen abiertos y no se amplió el alcance para corregirlos. Véase
[BATCH_5C_REMAINING.md](BATCH_5C_REMAINING.md). La revisión de cierre previa y
la revisión puntual de diagnóstico quedaron interrumpidas al cambiar la orden;
no se les atribuye aprobación. **No hubo revisión Opus fuera del punto 3 tras
la instrucción económica**. La única revisión final autorizada reprodujo sellos, contabilidad, elección,
identidad instalada y los dos P2 de D sobre build-08. Pasaron 33 pruebas focales
desde final-env. Los dos P2 no afectan la ejecución mecánica, pero impiden cumplir
la puerta vigente de cero P1/P2. Por eso aceptación permanece cerrada. La anotación semántica se aplaza, sin borrar los defectos conocidos.
Haiku fue solo el sistema evaluado, nunca un revisor ni escritor del proyecto.

## Demo, preservación y pendientes humanos

Demo instalada previa: input válido model_z=1.0745, inválido rechazado, caso de
línea única ambiguo y llamada MCP. A/B proviene de seis NPZ ya persistidos,
10.000 casos por semilla 17/42/101: diferencias de outliers A−B −1,21/−7,32/−3,05 pp,
con MAE normalizado peor para A en 17/101. No demuestra mejora uniforme.
139/150→119/150 sigue visible como resultado histórico de otra política.
No se afirma foundation model, independencia física ni superioridad CNN/v2.1.

Preservación comprobada: 1.174 archivos, 11.748.875.685 bytes, cero diferencias;
CSV previo FM sigue sin versionar, candidatas previas intactas. No es respaldo
independiente. [Acciones humanas](BATCH_5C_HUMAN_ACTIONS.md): H-18 con seis
preguntas sin respuestas atribuidas, respaldo independiente y publicación
pendientes. No hay casos de aceptación para adjudicar; anotación semántica IA
queda para otra sesión. El criterio general de C_pair=0 sigue pendiente.
Ramas codex/lote-5c, commits locales; sin push, merge, despliegue o publicación.

## Cierre del alcance autorizado

[Dictamen final registrado](evidence/batch5c-final-review.json): revisó documentos
en CP 67d26a9 / FM 7a469c8 y código instalado build-08. Los cambios posteriores
son documentales: estado de credencial, resultado final y corrección de EF-P3-1
(dos frases que aún decían reconstrucción en preparación). No se atribuye
a Opus una revisión de esos cambios posteriores. No se hizo otra revisión,
reconstrucción, llamada de generación ni anotación semántica.
La adenda 5C-2 no se activa: una futura apertura requiere resolver los bloqueos
bajo una nueva instrucción y registrar el protocolo/identidad antes de materializar.
Este es un cierre técnico local, no aceptación aprobada ni publicación.
