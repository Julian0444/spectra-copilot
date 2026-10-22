# 5B-2.2 — Haiku 5.5, presupuesto exacto y capacidad de entrada

Fecha: 2026-10-22. Implementación y comprobación dentro de esta sesión;
**no verificación independiente, no 5C**. 5B-2.1 permanece cerrado.

| Estado | Resultado |
|---|---|
| Migración del ejecutor | Implementada: claude-haiku-5-5 fijo; thinking adaptive, effort low; refusal/max_tokens terminales y model_z conservado |
| Límites | Actualizados mediante adenda autorizada; prefijo anterior de 22.515 bytes intacto en ambos repositorios |
| Presupuesto | Nanodólares enteros en reservas, liquidaciones y agregados; una fuente para límites, worker y CLI |
| O-5B21-01 | Corregido: fidelidad incluye status recomputado desde todas las observaciones |
| Capacidad en desarrollo | Medida con conteo gratuito de entrada y respuestas simuladas |
| Comportamiento real de Haiku 5.5 | **NO validado**; ninguna llamada que genere respuestas |
| Piloto pago sobre desarrollo | Decisión pendiente de Julian; **no ejecutado** |

## Fuentes y decisiones previas a la medición

Consultadas el 2026-10-22: [modelo y tarifas](https://platform.claude.com/docs/en/models/haiku-5-5/overview),
[precios](https://platform.claude.com/docs/en/about-claude/pricing),
[migración](https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide),
[IDs fijos](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions),
[facturación del razonamiento](https://platform.claude.com/docs/en/build-with-claude/thinking)
y [conteo gratuito](https://platform.claude.com/docs/en/build-with-claude/token-counting).
Las tarifas coinciden con la autorización: hasta 100.000 tokens de prompt,
US$0,10/M entrada y US$0,50/M salida; por encima, US$0,50/M y US$2,50/M.
Se registra la segunda tarifa y se rechaza esa franja antes del POST.

El ID sin fecha es fijo; no es el alias histórico de Haiku 4.5. Se eligió
thinking adaptativo y esfuerzo low a priori, con 4.096 tokens por llamada para
razonamiento y salida. No es una configuración calibrada mediante respuestas
reales. No se envían muestreo, prefill, fallbacks, caché, herramientas de servidor,
MCP, streaming ni edición de contexto. El historial enviado solo admite adiciones;
las trazas saneadas son copias. Los bloques de thinking vacíos se conservan.

Anthropic 0.120.2 ya instalado admite los parámetros necesarios en tool_runner y
count_tokens; se comprobaron firmas, serialización y transporte. Entornos y
versiones no cambiaron; no hubo descargas. Se añaden hashes de fuentes SDK a la
candidata. Los registros, cifras y evaluador de Haiku 4.5 siguen históricos.

## T3: qué se contó y qué se comprobó

Se reutilizaron los 2.970 cuerpos verificados por hash del replay 5B-2.1:
48 reales + 48 sintéticos de desarrollo, 90 válidos y seis entradas inválidas
sin solicitud; 540 conversaciones de 3 a 8 turnos. Se cambiaron únicamente
model, max_tokens, thinking y output_config. System, schemas, mensajes y
respuestas simuladas permanecieron iguales. El endpoint de conteo recibe los
campos de entrada; max_tokens se omite porque limita generación, no forma parte
de su esquema. El cuerpo de generación completo se conserva para la cota.

**2.970 solicitudes HTTP a count_tokens, 2.970 respuestas válidas, cero 429 y
cero reintentos. Gasto US$0; generación cero.** Transporte limitado a la URL
HTTPS autorizada y ese POST; sin redirects, sin otros endpoints. Techo local
3.000 RPM, bajo los 5.000 RPM del nivel mínimo documentado; hasta tres intentos
solo para 429 respetando retry-after. Cualquier otro error habría detenido la
medición. La clave del Llavero se cargó únicamente dentro de ese proceso y nunca
se escribió en archivos o logs. El log contiene solo 30 filas JSON de agregados,
sin cabeceras. Cuerpos y filas permanecen en el directorio privado.

| Medida de entrada | Resultado |
|---|---:|
| Tokens contados por solicitud, mínimo / máximo | 3.935 / 27.165 |
| Máxima cota UTF-8 + 4.096 | 65.863 |
| Máximo cociente tokens / cota | 0,4129345611 |
| Media del cociente tokens / cota | 0,3435924810 |
| Máximo cociente tokens / bytes del cuerpo | 0,4419246657 |
| Cota ≥ conteo + margen de 4.096 | 2.970/2.970, 100% |
| Holgura mínima adicional después del margen | 5.053 tokens |
| Umbral superior de la franja económica | 100.000 tokens |

Los recorridos de **3, 4, 5, 6, 7 y 8 turnos caben 90/90 cada uno**, incluso
liquidando toda la reserva de entrada y max_tokens de salida en cada llamada.
El mismo recálculo con entrada contada y salida máxima también da 90/90.
La comprobación aritmética separada de esta sesión no es revisión independiente.

Límites derivados: ocho cotas de 100.000 → 800.000 entrada acumulada;
ocho salidas de 4.096 → 32.768 salida acumulada, incluyendo thinking.
Máximo teórico exacto: **US$0,096384/caso y US$12,337152/128**. El peor recorrido
simulado consume reservas por US$0,0452148. Los techos US$0,10/US$12,80,
8 turnos, 6 tools, 1 intento, 0 retries y 120 s permanecen sin cambio.
Producción sigue con presupuesto cero por defecto. Uso desconocido o reserva
en vuelo no equivale a cero: detiene los casos restantes sin certificar coste.

**Límite de interpretación:** count_tokens estima entrada; las respuestas son
simuladas y no incluyen thinking generado por Haiku. Los historiales reales
pueden crecer de otra manera. Que quepan 90/90 recorridos de ocho turnos no prueba
finalización, cumplimiento del tiempo, calidad ni uso correcto de herramientas.
No se ajustaron criterios, rúbrica, selección ni umbrales de calidad.

Agregado versionado: [batch5b22-tokens.json](batch5b22-tokens.json), SHA-256
`420d5a3171b4869658740dbb03b33af69b545c431670592c8e75590fccc06724`.
Hashes de cuerpos/filas y preparación están en ese agregado; no se publican filas.

## Regresiones, identidad y preservación

Rojo/verde en commits separados: presupuesto/configuración
`023cb54` → `ba720b0` (6 fallos → 18 pases; 61 regresiones relacionadas),
paradas/historial `dd810de` → `6cfaaa3` (6 fallos válidos → 32 pases relacionados),
contabilidad integral `08d39bb` → `483dc2c` (2 fallos → 20 pases relacionados),
scorer `5fce89a` → `009d3d1` (2 fallos → 25 pases relacionados).
Las siete mutaciones exigidas se detectan, cada una con baseline verde:
precio histórico, CASE_MAX_USD antiguo, redondeo a microdólares, output_config
arbitrario, prompt superior a 100.000, refusal no terminal y scorer sin status.
Reproductor `scripts/check_batch5b22_mutations.py` de Copilot.

Suite completa Copilot: **317/317 en Python 3.12.13**. FM, modificado solo en
documentación/evidencia: **189/189 en Python 3.9.6 y 189/189 en 3.12.13**.
Protocolo/identidad tras la adenda: 46 pases. Red bloqueada en pruebas y procesos
hijos; T3 fue el único paso autenticado de red. pip check correcto.

Candidata nueva [batch5b22-candidate.json](batch5b22-candidate.json):
archivo `738649a1dc416f5f228564971f90b05ee50d3118858d094f086becf03320b471`;
comportamiento `136a1b1228f0635c207546d29710bc752f6a1c8aa6b2cdb62e44901ccc13326f`.
Verificada contra fuentes, activos, entorno y ambos directorios de protocolo.
[Diff por componente](batch5b22-candidate-differences.json): modelo, tarifas,
límites, presupuesto, agente, worker, scorer, registro de identidad, estados y
protocolo; el evaluador solo recibe un rótulo histórico. SDK sin cambio de versión,
con huellas añadidas. Prompt, schemas, corpus, predictor y activos científicos no
cambian. Candidatas de 5B-2 y 5B-2.1 íntegras. **No es identidad final instalada.**

1.174 archivos históricos iguales por SHA-256/tamaño al inicio y al final;
cero diferencias/extras. CSV FM sin versionar preservado. Selector, desarrollo y
compromiso conservan sus hashes. Aceptación privada se verificó solo por hash y
checker de custodia: `b8482511783a4d970693c650cd7046274303732643c13f95fdf03de9c9ae6a05`;
no se inspeccionaron, materializaron ni ejecutaron sus casos.

Incidencias conservadas: un primer fixture del SDK retenía un mock anterior;
se corrigió antes del rojo válido. El checker marcó siete copias no ejecutadas
del test del generador fuera de su ruta permitida, idénticas al original y sin
IDs/etiquetas privadas; se retiraron y se limitó la copia de fixtures, sin cambiar
el checker. Un intento de esa reducción omitió una dependencia de test y falló
la colección; no cuenta como mutación detectada. La repetición final dio 7/7.
Los barridos posteriores pasan; alcance final y logs en el handoff privado.

Originales en `codex/lote-5b-2-2`; `codex/lote-5b` conserva el cierre anterior.
Directorio privado: `/Users/jirustaroure/.local/state/spectra-consolidation/lote-5b-2-2-20261022-recvy0zo`.
Sin generación, gasto, nueva inferencia sobre test 4B, entrenamiento científico,
push, merge, publicación o despliegue. Respaldo independiente y rotación de claves
siguen sin verificar; H-18 sigue pendiente de Julian.

**Siguiente paso:** verificación independiente de 5B-2.2; después decisión de
Julian sobre piloto pago en desarrollo; por último autorización de gasto para
5C. Esta sesión se detiene en el cierre documentado de 5B-2.2.


Cierre adicional de límites suministrados por código: regresiones `1fb09b9`
(dos fallos) y corrección `e6fb325`. El agente conserva el máximo de ocho turnos,
4.096 de salida y 120 s aunque el presupuesto del llamante pida más; puede
restringirlos. Suite final `full-cp312-closure`: 317 pases. La primera repetición
tras actualizar README encontró una aserción de documentación aún fijada al ID
4.5; se actualizó al ID autorizado y la suite completa pasó. Las siete mutaciones
se repitieron en `mutations-closure/` contra este código, con siete baselines verdes.

La primera captura de candidata de esta sesión nunca se comprometió ni entregó;
se conserva como `candidate-before-final-caps.json` en privado. Tras estas
regresiones se capturó y verificó la candidata final de 5B-2.2 registrada arriba.
Las candidatas de las sesiones 5B-2 y 5B-2.1 no se modificaron. La configuración y
los cuerpos medidos de T3 no cambiaron con este refuerzo; no se repitió el conteo.
