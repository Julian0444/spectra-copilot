# Lote 5C — cierre experimental negativo; entrega técnica local

El piloto único se detuvo tras el primer intento con consumo desconocido.
La puerta de aceptación falló. No se eligió variante, no hubo confirmación,
no se abrió aceptación y no se publica una aceptación científica. La instalación
local 0.3.0, los controles de ejecución y la demo sí tienen evidencia independiente.

Fuente canónica del piloto: [batch5c-pilot.json](evidence/batch5c-pilot.json).
Este informe se refleja en ambos repositorios. Evidencia privada completa en
lote-5c-20261025-f50jj9q_, con comandos, logs, sellos, identidades y revisiones.
La entrega instalada posterior es build-06; se distingue de build-05, usado en el piloto.
D terminó bloqueado con dos P2 abiertos; la revisión/adjudicación sigue sin habilitar.
Los controles instalados y la demo no resuelven esos dos bloqueos.

## Piloto y puerta

La selección registrada conserva 12 casos de desarrollo: 4 reales
(2 CNN train, 2 validation) y 8 sintéticos, uno por familia. Cada variante
tiene 11 inputs válidos y uno inválido. Los 24 renglones se persistieron antes
de ejecutar; los pendientes permanecen en el denominador.

| Variante solicitada | Solicitados | Intentados | Informes válidos con obligaciones | Error técnico | Pendientes |
|---|---:|---:|---:|---:|---:|
| low | 12 | 1 | 0/11 válidos | 1 | 11 |
| medium | 12 | 0 | 0/11 válidos | 0 | 12 |
| Total | 24 | 1 | 0/22 válidos | 1 | 23 |

Hay una reserva de llamada en la frontera del SDK y cero reintentos.
Gasto conocido liquidado: US$0; **gasto total desconocido, no certificado**.
Reserva retenida: US$0,0035706. No equivale a una factura ni demuestra gasto cero.
Techo autorizado de la fase: US$2,40, sin transferir saldo a otras fases.
Medium tiene cero llamadas; eso no constituye una evaluación de medium.

La primera fila conservó model_z=1.0745 (1/1 predicciones disponibles), con
predict e identify en el ledger (2/6 análisis). Latencia del caso: 2,784 s.
Cotas de esa solicitud: 15.226 tokens de entrada y 4.096 de salida.
Tokens reales, thinking reenviado, stop_reason, aceptación de cabecera beta,
modelo devuelto y esfuerzo efectivo no se verificaron por falta de respuesta.
El modelo solicitado fue claude-haiku-5-5, thinking adaptive, effort low.

El error ocurrió dentro de la llamada SDK protegida. El arnés no conservó
tipo de excepción, código HTTP ni ID del proveedor; no se puede determinar
la causa remota, si el servicio recibió la solicitud o su facturación.
Se conserva esa limitación; no se hace otra llamada para diagnosticarla.
El cierre de fase está sellado y marca certified=false. El sello externo
se verificó antes de leer etiquetas de desarrollo.

La regla predefinida rechaza elegir con coste no certificado; no se sustituye
por medium. Fallan la cantidad mínima de informes (10/11), ausencia de fallo
técnico, ausencia de reserva y coste certificado. El inválido no llegó a
ejecutarse en ninguna variante: su rechazo experimental está pendiente,
aunque las pruebas offline sí comprueban rechazo sin POST.
Los ceros de max_tokens/refusal no prueban capacidad: faltan 23 ejecuciones.

Confirmación: **no ejecutada**, sin variante elegida y con gasto desconocido.
Aceptación: **no abierta ni ejecutada**; sus 128 casos (80 reales, 48 sintéticos)
siguen sin evaluación 5C. No se materializaron sus vistas ni se anotaron casos.
La adenda 5C-2 no se activa. No hay resultado científico de Haiku que puntuar.

## Software, instalación y comprobaciones

Ambos paquetes pasan de 0.2.0 a 0.3.0: los wheels 0.2.0 archivados representaban
solo el lote 2. Copilot requiere desi-fm >=0.3.0,<0.4. El entorno nuevo fue
instalado desde 104 wheels de dependencias registrados, fuera de los checkouts,
sin PYTHONPATH. Se verificaron module.__file__, RECORD, fuentes y recursos.

La instalación evaluada es build-05: FM fuente 2679d57 y Copilot 3b6de33;
wheels SHA-256 90da2025f456f0c6f8868bbcb683fb25a214b09ccb1b0ade746deb3ec98db64c
y 5ab9d8a81bfed18424c488d39d21978ff0deb1489ad3c5ae40c584269c401b92,
respectivamente. El entorno, wheels, protocolo y activos se congelaron antes
del intento; no se reinstaló durante la fase.

La entrega posterior build-06 usa release-env, otro venv nuevo: FM f27fb49 y
Copilot 0cdc6ea. [Manifiesto de entrega](evidence/batch5c-delivery.json) con wheels,
RECORD, identidades y hashes. Cambian únicamente cuatro módulos de Copilot respecto
del piloto: acceptance_score, review, review_annotations y review_packet; ningún
módulo FM. Sus huellas llm_path low/medium son idénticas a las del piloto.
Pasaron 15 pruebas de revisión contra los módulos instalados y la demo completa.
Dos intentos preparatorios de colección carecían de helpers de fixtures; están
preservados y no cuentan como pruebas ejecutadas. No se repite una suite general
ni se atribuye aceptación a build-06. Las interfaces B se apoyan en igualdad de
fuentes y dependencias; no se afirma otra corrida HTTP completa de build-06.

[Diferencias frente a 5B-2.2](evidence/batch5c-from-5b22-differences.json):
guardas/bootstrap/campaña, modo desarrollo, revisión y versiones; fecha de
verificación de precios; protocolo ampliado; procedencia de instalación y huella
adicional SDK beta. Los scripts auxiliares de checkout no van en el wheel y
quedan como null en esa identidad, sin fingir que se instalaron. Prompt, corpus,
schemas de herramientas, activos, predictor, política y contrato de entrada
siguen iguales. Las versiones comparadas de Python/paquetes también coinciden.

A incorporó bootstrap predict→identify, ambas observaciones en el mensaje
inicial, cautela sobre toda la evidencia, esfuerzo low/medium autorizado,
campaña única por fase, contabilidad entera y registro antes/después de POST,
plazo absoluto, bytes de inputs verificados, SDK beta en la identidad y
guardas de instalación. Las correcciones están documentadas con rojo→verde.
La suite de fuentes de A tuvo 338 pases y dos expectativas históricas
desactualizadas; después se corrigieron y pasaron las dos pruebas dirigidas.
No se presenta esa corrida inicial como una suite íntegramente verde.

B comprobó CLI, API upload/JSON/422, las cinco tools MCP por stdio con errores
de dominio y de esquema y recuperación, 16 recursos, y Gradio local mediante
upload/predict HTTP con masking 0/0.35 e inválidos. La campaña offline atravesó
el worker real sin POST. No se probó despliegue ni hosting público.
Python 3.12.13, macOS 26.6.2 arm64; otras plataformas no comprobadas.

Las huellas low/medium iniciales se conservaron. Antes del primer pago se
commiteó una enmienda explícita por dos correcciones demostradas:
normalización de rutas y validación de la proyección llm_path. Las huellas
build-05 son 8d79a71d…/537e07b9…; Opus las reconstruyó independientemente.
No cambiaron selección, regla de elección, puerta, prompt, límites ni tarifas.
El protocolo previo sigue intacto como prefijo.

## Qué revisó cada modelo

Codex GPT-6 Astra, esfuerzo xhigh declarado por el runtime, coordinó e implementó
código y documentos. Las pruebas de fuentes se distinguen de las de instalación.
Claude Opus 5.5 trabajó en clones propios de commits identificados, sin API paga
ni clave. Effort xhigh y fastMode=false fueron seleccionados; no son una
atestación del esfuerzo efectivo por el proveedor.

- A-6 y D: propuesta independiente y crítica cruzada antes de implementar.
- A: dos revisiones del delta; detectaron financiación insuficiente que consumía
  un intento, fixture del worker rota y rutas relativas inválidas. Se reprodujeron
  y corrigieron. La única comprobación adicional, autorizada expresamente por
  Julian, cerró los dos últimos P2 con 24 pruebas y mutaciones dirigidas.
- B: dos revisiones. Cerró la discrepancia de huella y el protocolo mutable;
  verificó ruedas/fuentes/registro. Aprobado, sin P1/P2. Las observaciones sobre
  activos, bytecode y congelación se aplicaron al lanzador antes del intento.
- D: la primera revisión encontró un P1 y tres P2 en adjudicación de inventario,
  ruptura de ceguera, enlace de anotaciones y contrato de datos. Codex los
  reprodujo y corrigió. La segunda revisión sobre 0cdc6ea cerró los cuatro,
  pero dejó dos P2 nuevos: adjudicación que puede borrar acuerdos y tratamiento
  ambiguo de extractos citados. Codex reprodujo ambos contra build-06 instalado.
  D queda bloqueado; se agotaron las dos rondas, sin pedir otra.
- Haiku 5.5: solo objetivo de la aplicación. No participó del trabajo de
  desarrollo/revisión y no produjo una respuesta utilizable en este intento.

[Bloqueos y reproducciones](BATCH_5C_REMAINING.md): no se corrigieron ni se
certificaron los dos P2 nuevos al agotar las rondas. No hubo revisión semántica de aceptación. El procedimiento preparado contempla
dos sesiones nuevas e independientes, paquetes equivalentes con identidad oculta,
anotaciones guardadas y hasheadas antes de compararlas y adjudicación de Julian.
La revisión sería por IA; Opus y Haiku comparten proveedor. No se la llama revisión
humana ni se presentan sus métricas todavía.

## Demo, A/B y límites científicos

[Reproducción](BATCH_5C_REPRODUCE.md): instalación offline con versiones/hashes,
rutas configurables, CLI/API/Gradio/MCP. La demo de desarrollo comprobó entrada
válida (model_z 1.0745), inválida rechazada, línea única ambigua y lookup_reference
por MCP, con cero llamadas pagas. La comparación A/B canónica está en FM,
docs/BATCH_5C_AB.md, sus PNG/SVG y batch5c-ab-persisted.json. Se leyó únicamente
predicción persistida, sin inferencia ni selección nueva.

A tuvo 1835/1489/1997 outliers y B 1956/2221/2302 sobre 10.000 casos por semilla
17/42/101: diferencias −1,21/−7,32/−3,05 puntos porcentuales. La MAE normalizada
de A empeora en 17 y 101; los resultados no son uniformes ni una conclusión
general sobre otras semillas. Se mantiene el resultado histórico negativo
del agente: **139/150 frente a 119/150**.

v2.1 sigue por defecto; CNN-17 experimental; model_z oficial. No hubo
entrenamiento, splits nuevos, selección de checkpoints, inferencia sobre test 4B
ni ajuste con aceptación. No se afirma foundation model, independencia física
o superioridad CNN/v2.1.

## Preservación y acciones humanas

[Verificación de preservación](evidence/batch5c-preservation.json):
1.174 archivos, 11.748.875.685 bytes, cero diferencias por SHA-256/tamaño,
incluido el CSV previo de FM, que sigue sin versionar. Candidatas anteriores
y artefactos históricos se conservan. Un inventario no es respaldo independiente.

[Acciones humanas](BATCH_5C_HUMAN_ACTIONS.md): H-18 sigue pendiente, con seis
preguntas preparadas y ninguna respuesta atribuida. La adjudicación no tiene
casos porque no hubo aceptación. El criterio C_pair=0 sigue sin resolución
humana general; no se convierte en 100%. Falta respaldo en un destino
independiente y conciliación externa del intento con consumo desconocido.
Se consultó a Julian si prefiere cierre negativo o dejar esa conciliación pendiente;
la pregunta no autoriza repetir el piloto.

Clave: **no rotada, por decisión de Julian; vence 2026-11-20**.
Ramas locales codex/lote-5c en ambos repositorios. Sin push, merge,
despliegue ni publicación. Cierre técnico local y resultado experimental
negativo no equivalen a aceptación científica aprobada.
