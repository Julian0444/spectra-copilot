# Preparación de ejecución 5C — no ejecutada en 5B-2

El protocolo y su adenda siguen en BATCH_5B_PROTOCOL.md. Esta guía no autoriza
pagos ni abre aceptación. La identidad registrada en 5B-2 es candidata. Primero
5C debe empaquetar, instalar en entorno limpio, verificar imports/activos,
registrar una identidad **final instalada** y justificar diferencias respecto
de la candidata. El colector actual rotula su salida como candidata; no equivale
a ese acto de registro final. v2.1 sigue por defecto; CNN-17 no se despliega.

Antes de cualquier corrida real Julian debe autorizar proveedor/modelo fijado,
tarifas fechadas, política de reserva, 128 casos, límites de tokens/llamadas y
coste. La propuesta usa claude-haiku-4-5-20251001; ocho turnos, seis tools contando
predict, un intento, cero retries, 64.000 input/4.096 output acumulados y 512 output
por turno. US$0,10/caso, US$12,80 global; límite estimado por tokens US$10,81344.
El presupuesto por defecto permanece cero. No usar claves en argumentos, logs
ni manifiestos. El código no solicita claves ni descarga activos.

## Custodia de entradas y etiquetas

Un custodio de 5C materializa los inputs científicos desde la selección sellada,
verifica su identidad y les asigna alias efímeros aleatorios de 24 hex (distintos
de los IDs de custodia). Preparar dos vistas privadas separadas:

- Plan `batch5c-inputs-v1`: solo `schema`, `mode: proposal`, `inputs`. Cada entrada
  contiene únicamente `alias`, `input_path` absoluto y `input_sha256`. Exactamente
  128 entradas, sin familia, exposición, redshift, respuestas esperadas o nombres
  que den pistas al LLM. El ejecutor sanea el NPZ a cuatro arrays y unidad antes
  de presentar un path opaco al agente. El mapa alias–custodia queda privado.
- Vista `batch5c-scoring-v1`: `schema`, `cases`. Cada fila contiene alias, kind,
  family cuando aplica, cnn_exposure, expected_answer y recipe sintética cuando
  el oráculo incluye admissible_z. No pasa al ejecutor ni a ninguna herramienta.
  Solo el proceso de puntuación la abre tras verificar el sello de las salidas.

No se prepararon estas vistas reales en 5B-2. Las únicas ejecuciones fueron con
fixtures inventadas. No se debe reutilizar la cohorte histórica como aceptación
nueva; los sintéticos de recetas públicas se informan separados de los reales.

## Orden de ejecución y persistencia

`python -m copilot.acceptance` recibe `--inputs`, `--output`, `--candidate`
(ruta a la identidad de ejecución registrada) y `--protocol-dir`; `--budget-usd`
es cero por defecto. Verifica identidad local antes de crear salidas y de nuevo
en cada worker. Cada caso usa un proceso nuevo con timeout duro de 120 s, sin
retry. Se registran todos los casos como pendientes antes del primero.

Antes de cada POST se persiste la reserva y la predicción oficial disponible.
Un timeout conserva ese último estado; una reserva en vuelo implica coste no
certificado y detención de los casos restantes, que siguen como pendientes.
Un directorio existente no se reutiliza: la reanudación/reconciliación de un
intento de consumo desconocido requiere decisión en 5C, no un retry silencioso.
La latencia de cada caso incluye su proceso y carga; los timeouts cuentan 120 s.

Al acabar o interrumpirse de forma controlada se escriben outputs.json,
summary.json y seal.json con hashes, incluyendo errores/pendientes. Un corte que
impida sellar no permite puntuar. Las trazas saneadas omiten credenciales y rutas
locales; conservan mediciones y model_z. La vista LLM compacta solo tablas de
soporte, picos fuera del top cinco y procedencia repetida; el ledger conserva
las mediciones completas y nunca descarta interpretaciones candidatas.

`python -m copilot.acceptance_score --run <salidas> --labels <vista-privada>`
verifica los hashes del sello **antes** de abrir etiquetas. `--reviews` incorpora
anotaciones independientes con el formato de BATCH_5C_REVIEW.md. No usar este
comando con aceptación durante 5B-2. La puntuación conserva N completo, separa
reales/sintéticos, familia y exposición, y no sustituye model_z por z de catálogo.

Los candidatos B9 se calculan sobre lambda_observada (§5 del protocolo). El
admissible_z de receta es un oráculo aritmético del centro inyectado, comprobado
separadamente al puntuar; no obliga a inferir un centro invisible a SNR=0.
No se inventa un criterio de recuperación exacta del centro ruidoso ni se pasa
su metadata al LLM. La abstención/ambigüedad se puntúa con el denominador completo.

## Qué acepta y qué no acepta el software

Se separan conservación de model_z, fidelidad de ítems de plantilla a herramientas,
IDs, respaldo textual, ciencia, afirmaciones sin respaldo, abstención, finalización,
fallos, latencia y coste. Wilson se aplica por caso; no por múltiples afirmaciones
correlacionadas. Denominador cero se representa como no aplicable.

La igualdad de model_z y las plantillas fieles son controles de software, no una
mejora de precisión del LLM. Los juicios semánticos, sus desacuerdos/adjudicación
y obligaciones omitidas por caso requieren revisión independiente; un resultado
mecánicamente correcto no acepta ciencia automáticamente. El scorer mantiene el
estado de aceptación sin aprobar hasta esa revisión y la comprobación de todos
los criterios congelados. No declara cerrado el proyecto ni publica resultados.
