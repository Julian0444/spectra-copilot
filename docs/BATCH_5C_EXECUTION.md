# Ejecución 5C — configuración vigente

Julian autorizó 5C por fases el 2026-10-25. Proveedor Anthropic, modelo fijo
`claude-haiku-5-5`, thinking adaptive; piloto exclusivamente de desarrollo para
comparar `low` y `medium`. No hay fallback ni retries automáticos. Antes de
cualquier gasto se exige la adenda 5C-1 commiteada, instalación limpia e
identidad registrada por variante. Esta guía no declara el piloto ejecutado.

Los límites permanecen: 8 turnos, **6 llamadas de análisis en total**, 800.000
tokens de entrada acumulada, 32.768 de salida incluido thinking, 4.096 por
llamada, 120 s y US$0,10 por caso. El ejecutor hace predict y después
identify_spectral_lines al arrancar: consumen **2 de 6**, quedan como máximo
4 análisis solicitados por el LLM. submit_report no es análisis. Ambas
observaciones quedan en el ledger y se entregan al LLM al inicio; toda evidencia
recalcula el piso de cautela aunque el LLM no la seleccione. model_z sigue oficial.

Prompt con cota >100.000 se rechaza antes del POST. Tarifas oficiales verificadas
el 2026-10-25: US$0,10/M entrada y US$0,50/M salida hasta 100.000 inclusive.
Presupuestos separados: piloto 12 × 2 variantes, US$2,40; confirmación opcional
una vez 12, US$1,20; aceptación 128 una vez, US$12,80. Sin transferencias.
Uso desconocido o reserva en vuelo bloquea nuevos pagos y no certifica coste.
El tope por caso es más estricto que la **media** congelada ≤US$0,10/caso: no
modifica ese criterio de aceptación ni los denominadores. Presupuesto por defecto 0.

La medición de conteo anterior tuvo **90 válidos = 48 reales + 42 sintéticos**,
y seis sintéticos inválidos, sobre 96 de desarrollo. Son respuestas simuladas,
no evidencia del comportamiento real del LLM. Ver evidence/batch5b22-tokens.json.

v2.1 permanece por defecto y CNN-17 experimental. Aceptación cerrada hasta la
puerta D, sin modificar rúbrica/selección. Clave: **no rotada, por decisión de
Julian; vence 2026-11-20**. Solo se carga dentro del proceso autorizado, jamás
en argumentos, archivos o sesiones de revisión.

## Desarrollo y campaña 5C

El materializador empaquetado `python -m copilot.development --manifest <desarrollo>
--output <nuevo> --raw-root <datos-locales> --index <sqlite>` solo abre el manifiesto
con SHA-256 `60b2b4584e5a57030a4ff82a1b13d23065505a4d8bb878a20f5d4caecbe3f7c4`.
Recalcula los 12 casos y produce por separado NPZ, registro, plan y etiquetas de
desarrollo. No requiere ni lee aceptación. El registro comprometido vive en
`docs/protocol/batch5c-development-registry.json`; todo input debe coincidir por
hash de bytes y arrays. El soporte inválido pertenece al registro y el worker lo
rechaza antes del LLM.

`python -m copilot.campaign init --directory <campaña> --protocol-dir <docs>`
crea una sola vez la campaña cuyo ID y hash de ruta están comprometidos en
`docs/protocol/batch5c-campaign.json`. Cada fase reclama un único intento; una
fase abierta o cerrada con gasto no certificado bloquea las siguientes. No se
reutilizan directorios, reclamos ni sellos. Antes del reclamo se exige presupuesto
suficiente para todas las filas: mínimos US$2,313216 / US$1,156608 / US$12,337152
para piloto / confirmación / aceptación, dentro de sus techos autorizados.

El plan `mode: development` incluye `phase`, `registry_sha256` y esfuerzo por fila.
Piloto: 24 filas, pares low/medium para slots pares desde cero, medium/low para
impares. Se ejecuta con `python -m copilot.acceptance --inputs <pilot-inputs.json>
--output <nuevo> --candidate <identidad-low> --candidate-medium <identidad-medium>
--effort low --campaign-dir <campaña> --protocol-dir <docs> --budget-usd 2.40`.
Cada identidad debe corresponder a los wheels instalados. El worker recaptura la
identidad y exige reclamo abierto, rutas, input, esfuerzo y alias coincidentes;
un marcador exclusivo impide un segundo worker para la misma fila. Ni
`copilot.agent` ni el worker aislado autorizan gasto fuera de ese circuito.
La clave se carga solo dentro del proceso autorizado, nunca en esta línea de
comandos. El ledger y `paid-calls.jsonl` se sincronizan antes/después de cada POST.

Confirmación: los mismos 12 slots, solo el esfuerzo elegido, máximo US$1,20,
una vez y únicamente tras corregir un defecto demostrado del camino LLM. La
adenda 5C-1 fija elección y puerta antes del piloto; esta guía no las sustituye.

## Aislamiento del proceso instalado

Usar el intérprete absoluto `<venv>/bin/python -I -B`, cwd privado fuera de los
repos, sin PYTHONPATH, y `--protocol-dir <protocolo-congelado>/docs`. El comando
de arriba muestra argumentos; esos tres requisitos son obligatorios. Captura,
padre y workers comparten ese protocolo y las copias verificadas de activos
(`DESI_FM_CKPT`, `DESI_FM_INDEX_DIR`). No apuntar a docs/ o data/ editables durante
la campaña. El apéndice prepiloto de 5C-1 y su registro nuevo sustituyen las
huellas previas únicamente antes del primer pago; ambos registros se conservan.

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
impida sellar y registrar su hash no permite puntuar. El ejecutor crea además
`<salidas>.seal-record.json`, como hermano del directorio de salidas, con el
SHA-256 del sello. Nunca sobrescribe ese registro. El custodio debe conservarlo
fuera de las salidas y llevar su hash al registro de la corrida antes de puntuar.
Es una referencia externa de integridad; no equivale a almacenamiento inmutable
ni a verificación independiente. Las trazas saneadas omiten credenciales y rutas
locales; conservan mediciones y model_z. La vista LLM compacta solo tablas de
soporte, picos fuera del top cinco y procedencia repetida; el ledger conserva
las mediciones completas y nunca descarta interpretaciones candidatas.

`python -m copilot.acceptance_score --run <salidas> --labels <vista-privada>`
exige el registro externo (por defecto el hermano anterior; `--seal-record`
permite indicar otra ruta externa), contrasta el SHA-256 del sello y los hashes
de archivos, el orden de alias y `summary.outputs_sha256` **antes** de abrir
etiquetas. Rechaza también un enlace que resuelva dentro de las salidas.
Registra el instante de verificación, inicio y fin de lectura de etiquetas;
`seal_verified_before_label_read` se calcula a partir de esos eventos.
`--reviews` incorpora
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


---

# Historia de preparación 5B-2 / 5B-2.2

El protocolo y su adenda siguen en BATCH_5B_PROTOCOL.md. Esta guía no autoriza
pagos ni abre aceptación. La identidad registrada en 5B-2 es candidata. Primero
5C debe empaquetar, instalar en entorno limpio, verificar imports/activos,
registrar una identidad **final instalada** y justificar diferencias respecto
de la candidata. El colector actual rotula su salida como candidata; no equivale
a ese acto de registro final. v2.1 sigue por defecto; CNN-17 no se despliega.

Antes de cualquier corrida real Julian debe autorizar proveedor/modelo fijado,
tarifas fechadas, política de reserva, 128 casos, límites de tokens/llamadas y
coste. La propuesta histórica de 5B-2 usaba claude-haiku-4-5-20251001; ocho turnos, seis tools contando
predict, un intento, cero retries, 64.000 input/4.096 output acumulados y 512 output
por turno. US$0,10/caso, US$12,80 global; límite estimado por tokens US$10,81344.
El presupuesto por defecto permanece cero. No usar claves en argumentos, logs
ni manifiestos. El código no solicita claves ni descarga activos.

5B-2.1 midió las solicitudes reales del SDK con transporte simulado sobre todo
el desarrollo. La cota por bytes puede detener recorridos antes de ocho turnos;
no se ha demostrado factibilidad para el LLM real. Las dos opciones, costes
máximos condicionados a las tarifas registradas y limitaciones están en
[batch5b21-budget.md](evidence/batch5b21-budget.md). 5B-2.1 ya tiene revisión
independiente. La actualización posterior se registra abajo.

## Registro histórico 5B-2.2 — 2026-10-22

La adenda autorizada en BATCH_5B_PROTOCOL fija `claude-haiku-5-5`, thinking
adaptativo y esfuerzo low, 800.000 tokens de entrada acumulada, 32.768 de salida
y 4.096 por llamada. La cota por solicitud no puede superar 100.000. El máximo
teórico es US$0,096384/caso y US$12,337152/128 casos; los techos absolutos
US$0,10/US$12,80 y todos los límites de calidad, turnos, tools y tiempo se conservan.

La capacidad se comprueba únicamente con count_tokens gratuito y el replay
simulado de desarrollo; véase `evidence/batch5b22-tokens.json` y su explicación.
Eso no valida comportamiento real, finalización ni latencia del modelo.
Presupuesto por defecto cero. La nueva candidata es de 5B-2.2, no una identidad
final instalada. Siguiente orden: verificación independiente de 5B-2.2,
decisión de Julian sobre piloto pago en desarrollo y, por último, autorización
de gasto para 5C. Nada de ello se ejecuta en esta sesión.
