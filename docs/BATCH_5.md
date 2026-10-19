# Lote 5 — consolidación por fases

## 5A (entrega técnica local, 2026-10-16)

Alcance vigente: A documentación → E MCP/evaluador/fallos → B contratos/regresiones.
5A no incluye política explicativa, rediseño del matcher, aceptación CNN, LLM
real, instalación limpia, publicación ni reconstrucción FAISS. v2.1 sigue por
defecto; la protección de model_z aún NO está implementada (5B).

Bases exactas: FM 4387dd36c6ad640f00c6d9fc3bf6448ef3644d50; Copilot
6d4d8ed8acaeeec0d7cba64b37421f6459ce5c6e. Ramas nuevas `codex/lote-5a` en
los originales. Solo FM tenía `runs/desi_50k_big/predictions_heldout.csv`
sin versionar; se conserva y no se añade. Directorio privado nuevo:
`~/.local/state/spectra-consolidation/lote-5a-20261016-6bz7d49b/`.
Estados, logs, cachés, temporales e inventarios allí; no se modifica el entorno
histórico ni se hacen llamadas pagas. Los imports de pruebas apuntan a fuentes.

### A: resultado y límites

En los tres pares de checkpoints seleccionados mediante la regla de validación,
A tuvo menos outliers que B y se cumplió el criterio predefinido. La generalización
del beneficio a otras semillas o checkpoints no está establecida. El intervalo
principal está condicionado a esos pares. A empeora en objetos con advertencia;
su MAE empeora en 17 y 101; la mejora media la impulsa 42. La CNN ganó una
comparación práctica que también cambia entrada durante entrenamiento. El
12% histórico de v2.1 y el 9,29% de CNN en otro test no miden superioridad.
El único resultado medido del agente sigue siendo negativo: 139/150 → 119/150.

Los recálculos posteriores de FM `scripts/analyze_batch5a.py` leen NPZ persistidos
y metadatos sin inferencia: tabla de 180 validaciones, diferencias por paso,
márgenes de selección, promedios de los k mejores scores y ΔMAE por semilla.
No son reglas nuevas ni autorizan elegir otros checkpoints. No se añade un
intervalo entre semillas como sustituto del análisis predefinido (n=3 es escaso).
JSON/figuras congelados se preservan. Copilot remite a la evidencia FM.

No existen columnas explícitas RA/DEC; `object_id` procede de TARGETID según el
[conversor fijado](https://github.com/MultimodalUniverse/MultimodalUniverse/blob/0c77e592470c3dc92147ee7d02f7e5cb65b8ebd5/scripts/desi/desi.py).
La [definición oficial de bits](https://github.com/desihub/desitarget/blob/main/py/desitarget/data/targetmask.yaml)
asigna OBJID 0–21, BRICKID 22–41 y RELEASE 42–57. Las
[releases 9010/9011](https://www.legacysurvey.org/release/) corresponden a DR9;
[BRICKID identifica una celda de cielo](https://www.legacysurvey.org/dr9/files/).
La comprobación restringe su aplicación a IDs DR9 sin flags mock/sky/Gaia/reservados
y con brick válido: 82.468/84.759 elegibles, 339 bricks en esa población.
9.720/9.721 IDs DR9 del test comparten brick con train. Localidad no identifica
observaciones repetidas de la misma fuente. No se rehacen splits ni se afirma
independencia física. La sensibilidad por brick sin cambios apreciables de
Claude es evidencia posterior, no prueba de efecto nulo ni de independencia.

De la cola histórica de 2.759 filas elegibles, 2.114 están en train CNN, 333 en
validación de selección y 312 en test 4B ya abierto, recalculado por ordinal/ID
desde SQLite y splits. No queda una reserva confirmatoria intacta. Una comparación
futura CNN/v2.1 requiere datos adicionales y control de solapamientos: otra
release DESI no garantiza independencia.

H-12: se inspeccionó la sonda CPU de Claude de 25 objetos y su salida; no se
repite inferencia en 5A. No extender el control original de nueve objetos ni la
repetición MPS exacta a todas las reconstrucciones CPU/MPS. El comparador exige
igualdad de huella de fuentes, no un commit literal. Véase adenda BATCH_3.md de FM.

### Preservación y reproducción histórica

Inventario inicial SHA-256/tamaños completo: 658 archivos de lote-4b-01,
6.059.818.657 bytes; 18 archivos de batch4a-v1, 3.014.928.724 bytes; juntos
**9.074.747.381 bytes (~9,075 GB)**. Preparación: 171 archivos / 87.279.004 bytes,
incluidas cachés existentes. También se inventariaron activos históricos locales.
No es un respaldo. **Respaldo independiente pendiente**: no hay destino
independiente autorizado; copiar los tres directorios a uno nuevo autorizado
y verificar tamaños y hashes. Otra carpeta en el mismo disco no basta.
Rotación de claves: **sin verificar**, no completada por documentar el pendiente.

Si cambia identidad científica en 5A, conservar las guardas: usar código registrado
para reproducir lo histórico, nunca actualizar hashes de run.json. Para obtener
ese código sin mover las ramas actuales, desde FM y con destinos nuevos:

```sh
git clone --no-hardlinks --no-checkout "/ruta/al/FM-original" /ruta/nueva/codigo-4b
git -C /ruta/nueva/codigo-4b checkout --detach 4387dd36c6ad640f00c6d9fc3bf6448ef3644d50
# Ejecutar con ese checkout como cwd/PYTHONPATH y con el entorno registrado.
# No mover el original ni modificar hashes de artefactos. No abre test por sí solo.
```

Para lote 3, código registrado `008ce03da7d8c3d74d522b03eedbf3d61b7e861a` y
el entorno/activos de su manifiesto. Esto documenta el camino histórico; no
certifica todavía reproducción portable ni autoriza otra inferencia de test.
Los wheels 0.2.0 archivados certifican exclusivamente el lote 2 y no contienen
el código vigente. Nuevas versiones y aceptación instalada quedan para 5C.

### Matriz H-01–H-18 (registro 5A; actualización 5B-1 al final)

| Hallazgo | Acción | Fase | Estado | Evidencia |
|---|---|---|---|---|
| H-01 conclusión | Acotar a pares seleccionados; sensibilidades posteriores | 5A A | Hecho | batch5a-analysis.md/json; BATCH_4B.md |
| H-02 superficies | Retirar imagen del recorrido; 12% histórico; hechos del prompt | 5A A | Hecho local | README/model card/report/MCP; publicación pendiente |
| H-03 concurrencia | Hilos FAISS, estado cacheado y stdio | 5A E | Hecho | batch5a-E.json; stdio concurrente |
| H-04 wheels | Rotular 0.2.0 como lote 2; nuevas versiones/instalación | 5A A / 5C | Texto hecho; paquete pendiente | README; BATCH_2.md |
| H-05 localidad | TARGETID/brick; no afirmar independencia física | 5A A | Hecho | batch5a-analysis.json; fuentes oficiales citadas en A |
| H-06 cobertura | Pérdidas/gradientes, normalización, métricas/guardas y mutaciones | 5A B | Hecho | batch5a-B.json; pruebas de gradiente/guardas y 18 mutaciones |
| H-07 reproducción | Preservar camino histórico; paquete portable/respaldo | 5A / 5C / externo | Preservación verificada; portable/respaldo pendientes | manifiesto privado; camino histórico documentado arriba |
| H-08 cronología | Declarar plan durante serie y apertura automática | 5A A | Hecho | Adenda BATCH_4B.md / ANALYSIS.md; timeline de Claude |
| H-09 solapamientos | Cola 2.114/333/312; excluir 4B de aceptación futura | 5A A / 5B | Límite documentado; congelado futuro pendiente | batch5a-analysis.json |
| H-10 selección B-101 | Margen 2 objetos y sensibilidad de estratos | 5A A | Hecho | batch5a-analysis.md; STRATA.md |
| H-11 comparabilidad | No comparar 12% histórico con 9,29% CNN | 5A A | Hecho | README/model card/BATCH_4B.md |
| H-12 reproducción lote 3 | Acotar dispositivos e igualdad de hash de código | 5A A | Acotado, no nueva inferencia | Adenda BATCH_3.md; sonda inspeccionada |
| H-13 residuos | Contratos, descripciones, corpus, conteos históricos | 5A A | Hecho local | diff de A |
| H-14 evaluador | Resumen atómico y fallos con salida no cero | 5A E | Hecho | test_failure_reporting.py; batch5a-E.json |
| H-15 huecos | Coordenadas ausentes/NaN, doble hueco, interfaces | 5A B | Hecho | contrato v3; 9 fallos antes y suite después |
| H-16 agotamiento | Estado explícito, trazas y salida CLI | 5A E | Hecho | test_failure_reporting.py; batch5a-E.json |
| H-17 alcance revisión | Separar recálculo, generador y efectos de caché | 5A A | Hecho | Corrección identificada en consenso §12.1 |
| H-18 autoría | Preguntas para Julian, sin respuesta atribuida | Humano | Pendiente | Preguntas abajo |

### Handoff 5B / 5C

1. Antes de cambiar política o matcher, definir y congelar desarrollo/aceptación
   con IDs y rúbrica. Excluir test 4B; no ajustar con los 150 históricos ni
   presentarlos después como aceptación ciega nueva. Resolver la reserva de datos.
2. Proteger model_z por código y separar alternativas; reproducir discriminación
   del matcher contra controles en desarrollo. Por defecto retirar “confirmación”
   sin respaldo y conservar medidas descriptivas; no buscar reglas indefinidamente.
3. Resolver B7/B9 y evaluar operativamente CNN-17 sin desplegarla ni afirmar
   superioridad frente a v2.1.
4. 5C: LLM real solo con modelo/muestra/límites/presupuesto autorizados; versiones,
   wheels, instalación aislada, CI, Gradio real, quick start, captura/demostración,
   paquete portable y preparación de publicación.

Preguntas breves para Julian (H-18, respuesta personal todavía pendiente):
- ¿Cuál era la hipótesis y qué resultado la habría debilitado?
- ¿Qué cambió entre A y B y qué se mantuvo emparejado?
- ¿Cómo se seleccionaron checkpoints y cuándo se abrió test?
- ¿Qué resultados favorecen A y cuáles contradicen una mejora uniforme?
- ¿Qué no permite concluir CNN/v2.1, n=3 o un brick compartido?
- ¿Qué decisiones y comprobaciones realizaste personalmente?

Punto de control A: recálculo sin inferencia completado, 18 pruebas de hechos/runner/tools Copilot aprobadas; diff sin errores de whitespace. Cambios de A son descripciones y evidencia, no nueva política ni algoritmo.

### E: entregado localmente

MCP: un RLock reentrante serializa las cargas cacheadas y las operaciones que
usan modelo/índice. Evita restauraciones solapadas de flags eval/train y cargas
duplicadas. FAISS configura un hilo en cada búsqueda, aunque el worker cambie;
no depende de OMP_NUM_THREADS del usuario. Se conserva el workaround existente
de doble runtime OpenMP; no se promete compatibilidad universal. Tools sin modelo
pueden solaparse. No se entrena concurrentemente el objeto servido.

Reproducción stdio adaptada de Claude: timeout real, salida 1, diagnóstico y
limpieza exclusiva del servidor creado. Tras corregir: nueve escenarios en
servidores nuevos, **170 llamadas reales sin fallos** (secuencial, búsquedas
solapadas, carga en frío, mixtas, búsqueda secuencial después de solapamiento).
macOS comprobado; Linux/Windows no probados. Las pruebas sintéticas stdio verifican
las cinco tools, entradas distintas, recuperación y ausencia de mezcla de respuestas;
los errores de dominio llevan `is_error` y `error.code=invalid_input`, con tipo.
Los errores de schema/tipo llegan como validación MCP/Pydantic. Timeout falla;
el transcript se conserva incluso si falla una aserción.

Evaluador: resumen atómico al lado del CSV y vinculado por su SHA-256, denominador
completo y estados explícitos; salida 0/2/3 para completo/parcial/cero válidos.
Reanudación e identidad intactas; históricos no adoptados. Ambos archivos son
atómicos individualmente: un corte entre reemplazos se detecta por el hash y se
repara al reanudar. Informe del agente agotado devuelve error explícito y CLI 2,
con traza saneada y sidecar de estado si se solicita transcript. No cambia política.

Regresiones E: 9 fallan en la copia anterior `188a38f`; 42 pruebas pertinentes
pasan después. El agotamiento usa SDK Anthropic real con HTTP simulado (ocho
respuestas tool_use, con/sin preámbulo), sin API remota. Evidencia Copilot:
`docs/evidence/batch5a-E.json`; comandos: pytest tests/test_failure_reporting.py
 tests/test_eval_persistence.py tests/test_evals.py tests/test_mcp_stdio.py
 tests/test_tool_concurrency.py -q -p no:cacheprovider, con PYTHONPATH a fuentes.

### B: contratos y regresiones comprobados

La intervención se verifica con pérdida observada en backward y gradientes antes
del clipping: la diferencia A−B coincide con la derivada reconstructiva calculada
con una MSE de píxeles independiente del sumador del Trainer. B tiene gradiente
reconstructivo cero y mantiene clasificación; A propaga reconstrucción al encoder.
Tres semillas, inicialización completa, muestras/posiciones/máscaras/inputs iguales.
Una perturbación de los píxeles ocultos a través de ExperimentData.batch no puede
cambiar centros, escalas ni píxeles visibles. Los registros de ejecuciones futuras
añaden coeficiente efectivo y pérdida total; ningún run.json histórico cambia.

Las pruebas de métricas usan errores constantes 0,125 / 0,15 / 0,16: exigen los
intervalos exactos y distinguen 0,10 de 0,15 y > de >= sin depender del RNG.
La guarda neural de entorno se aísla haciendo que ridge sí coincida con el entorno
actual. Se exige el error específico y ninguna carga de test, apertura o salida;
otras guardas no pueden producir un falso aprobado. También se prueba el
congelado con nueve candidatos y ridge de otro entorno homogéneo.

H-15: 9 casos fallaban antes (coordenadas ausentes/NaN/Inf × orden original,
invertido/permutado). Se usa el menor paso vecino para no puentear dos huecos
separados por una muestra. Contrato `spectra-input-v3`, derivado futuro
`batch4-grid-v2:unnormalized-spectra-input-v3`; es una regla local conservadora,
no una garantía física para cualquier muestreo. No se modifica el derivado 4B.
Índices de elegibilidad v2 y matrices v1 no se aceptan como nuevos derivados v3.
El lector raw por ID sigue pudiendo leer el índice verificado histórico.

La fixture gap elimina coordenadas y ya no equivale a masked. Se prueba falta de
wavelength, NaN/Inf, doble hueco, orden, mask/ivar y cobertura insuficiente. Los
handlers reales API (upload/JSON), demo, tester y tools predict/reconstruct reciben
mask e ivar hasta el tensor de validez del modelo. Gradio/Spaces solo se simulan
como anfitriones: esto no certifica UI instalada, hosting ni quick start (5C).

**Mutaciones acotadas:** 18 defectos detectados en copias temporales y un cambio
equivalente 1.→1.0 que pasa. Incluyen coeficientes cero/uno/invertidos, normalización
con ocultos, muestras/inicialización/máscaras no emparejadas, umbrales/límites,
ambas guardas de entorno, regla antigua de huecos y pérdida de calidad en
API/demo/tools. Cada baseline pasa; timeout/colección rota no cuentan como detección.
Reproductor FM: `scripts/check_batch5a_mutations.py --copilot /ruta/copilot
--output /destino/nuevo`; requiere intérprete de pruebas y PYTHONPATH a fuentes.
Evidencia ligera: [batch5a-B.json](evidence/batch5a-B.json), con comandos/mutaciones
y hashes de logs privados. No campaña general ni datos reales en esas sondas.

### Comprobación final de 5A

FM: 130 passed en Python 3.9.6 y 130 en 3.12.13. Copilot: 97 passed en 3.12.13.
Suites completas `python -m pytest tests -q -p no:cacheprovider`, imports desde
los originales mediante PYTHONPATH; no del wheel antiguo. Warnings existentes
PyTorch; en 3.9 también urllib3/LibreSSL y matplotlib/pyparsing. Sin omisiones.
`pip check` 3.12 pasa. El Python 3.9 global conserva conflictos preexistentes de
Copilot/MCP/Anthropic, torchvision/torch y grpcio: no se modifica ni se certifica
como instalación limpia; la suite FM sí pasa. Copilot requiere Python >=3.10.
Hay intérpretes 3.11.15 y 3.14.7 sin dependencias del proyecto; no se aprovisionaron
ni se probaron. Linux/Windows, Gradio real, wheels vigentes y portabilidad no se
certifican aquí. No llamadas reales al LLM ni inferencia nueva sobre test 4B.

El inventario posterior conserva exactamente los hashes y tamaños de los tres
directorios inmutables y activos locales inventariados. Se comprobaron además
74/74 históricos FM, 169/169 Copilot y siete parquet contra sus manifiestos.
Los 25 archivos científicos de FM `4387dd3` coinciden con frozen.json (huella
828a7187545d30c9dbab55a9b49cc64925cfbdbeaa9160f3f52567c6f6f2152c).
No se ejecutó el evaluador histórico: comprobar código preservado no es repetir
inferencia ni certificar portabilidad. Respaldo independiente, rotación de claves
y explicación personal de Julian siguen pendientes con los estados arriba.

### Commits y punto de continuidad

| Ticket | FM | Copilot |
|---|---|---|
| A: documentos/hechos/sensibilidades | d0b968c, e3ea253 | 188a38f, 619ecb8 |
| E: fallos y concurrencia | 82639aa (registro) | c589378, 76a41f8 |
| B: contratos, pruebas y evidencia | 913fdc9 | 3095458 |

Rama `codex/lote-5a` en ambos originales. HEAD de implementación comprobada:
FM `913fdc9561bf8ace10a4f640a2aa6246c99295c0`, Copilot
`3095458c443729e92d4ff71fa08f0ddfb3727a18`; el commit posterior de cierre añade
solo este registro/evidencia. Los HEAD de cierre se registran en el consenso §13.
FM conserva únicamente el CSV sin versionar previo; Copilot limpio. El consenso
se mantiene fuera de estos repositorios. No se añadieron secretos, pesos, datasets,
wheels, CSV históricos ni logs voluminosos. `git diff --check` aprobado.

**Registro histórico del cierre del 2026-10-16:** «5A técnicamente entregado: A, E y B implementados y comprobados. Ninguna
corrección obligatoria de esta fase queda abierta». Esta conclusión fue matizada
por R5A-01/R5A-02 y O-1; véase la adenda de correcciones al final. H-04/H-07/H-09 conservan sus
partes asignadas a 5B/5C o a acciones externas; H-12 queda acotado, sin promesa
portable. No se declara cerrado el proyecto. Véase [evidencia de cierre](evidence/batch5a-close.json).

Siguiente paso exacto: abrir 5B desde estos originales, registrar el nuevo estado
y **definir y congelar IDs de desarrollo/aceptación y rúbrica antes de editar
política o matcher**. Excluir test 4B y no reutilizar los 150 históricos como
aceptación ciega. La cola 2.759 ya está repartida 2.114/333/312 y no resuelve esa
reserva. Después: protección model_z/separación de alternativas, controles del
matcher, B7/B9 y evaluación operativa CNN-17 sin despliegue. Si el matcher no
sostiene discriminación, retirar por defecto “confirmación” y conservar medidas
descriptivas. No ajustar indefinidamente para salvar el veredicto.

Las acciones de 5C y las autorizaciones LLM siguen siendo independientes de esta
entrega. No se publicó ni se empezó 5B. Respaldar como mínimo lote-4b-01,
lote-4b-preparation-20261010 y batch4a-v1 en un destino independiente autorizado,
con directorio nuevo y verificación SHA-256/tamaños. Para la conservación completa,
incluir también raw/índice locales, pesos e históricos de ambos repositorios.


### Adenda 5A — R5A-01, R5A-02 y O-1 (sesión 5B-1, 2026-10-18)

Corrección identificada del cierre anterior: la frase «ninguna corrección
obligatoria de esta fase queda abierta» fue la conclusión del 16 de octubre,
matizada después por verificación independiente. Se conserva como registro
histórico; los pendientes confirmados se cierran con esta adenda.

| Ticket | Cambio y evidencia | Commit en codex/lote-5a |
|---|---|---|
| R5A-01 | Entrada ausente sigue invalid_input por el lector. Checkpoint/índice/caché offline y otros fallos internos devuelven internal_error/ServerExecutionError con is_error, sin rutas ni mensajes privados. Validación MCP/Pydantic intacta. | Copilot 40b9240 |
| R5A-02 | Eliminados conteos fijos en README.md, README.es.md y COMO_FUNCIONA.md; enlaces a esta evidencia. Barrido de superficies actuales de ambos repos; registros históricos conservados. | FM 594d16c |
| O-1 | Brecha de cobertura cerrada, no fallo funcional corregido: exclusión mutua, respuestas por solicitud y carga única observadas con hilos distintos para predict/reconstruct/find_similar/model/index, con stubs. tools.py no cambió. | Copilot ad26b6f |

R5A-01: las regresiones definitivas dan **9 failed, 3 passed sobre ef7d220** y
pasan después, incluyendo stdio real con timeout y recuperación tras crear el
activo sintético. Red bloqueada, cero intentos; sin pesos reales. El primer
ensayo tuvo además un error de teardown de la fixture, corregido y repetido;
ese error no se cuenta como detección. Errores de permisos/identidad/ejecución
se ensayan mediante stubs de las excepciones correspondientes.

O-1/R5A-01: **7 mutaciones detectadas** en copias nuevas: capturar cualquier
excepción como entrada, capturar FileNotFoundError como entrada y quitar
exclusión mutua por separado de las tres operaciones y dos cargas cacheadas.
Baseline y control equivalente acquire/try/finally/release: 21 pruebas aprobadas.
Las pruebas observan comportamiento, no exigen un decorador. Reproductor en
Copilot: `scripts/check_batch5a_followup_mutations.py --output <directorio-nuevo>`.

Suites completas: **FM 130 en Python 3.9.6 y 130 en 3.12.13; Copilot 115 en
3.12.13**, sin omisiones. Comando: `python -m pytest tests -q -p no:cacheprovider`,
PYTHONPATH a ambos checkouts, TMPDIR corto, cachés/logs privados. Imports
comprobados desde fuentes, no wheels antiguos; no se instalaron dependencias
ni se modificaron entornos históricos/globales. Advertencias preexistentes de
PyTorch y, en 3.9, LibreSSL/pyparsing. `git diff --check` pasa en ambos repos.
Los tests heredados usan el checkpoint local de demo; las regresiones nuevas
solo stubs/sintéticos. No inferencia del test 4B ni llamadas al LLM.

Preservación inicial contra inventario 5A: **1.174 archivos**, cero diferencias
de SHA-256/tamaño ni archivos extra en los tres árboles inmutables. Sigue
**no hay respaldo independiente verificado**. Rotación de claves: **sin verificar**.
H-18: **pendiente de Julian**, no se atribuye una respuesta. Evidencia ligera:
[batch5a-followup.json](evidence/batch5a-followup.json). Los HEAD corregidos
incluyendo este registro quedarán en el congelado y en el consenso.


## 5B-1 — protocolo congelado, sin iniciar 5B-2

Ramas exactas: **codex/lote-5b** en ambos originales, nuevas desde las ramas
5A corregidas, sin reiniciar ninguna referencia. Bases:

| Repo | HEAD corregido de codex/lote-5a |
|---|---|
| FM | c99ec856f968f2965a4b6ebd73c399fe2ecb107c |
| Copilot | 9c5cf0e232736a7a0ce386a487d218517a59de9c |

El primer commit propio de cada rama congela exclusivamente
[BATCH_5B_PROTOCOL.md](BATCH_5B_PROTOCOL.md), manifiesto de desarrollo,
compromiso, scripts de selección/comprobación de filtraciones, pruebas y esta
documentación. Los hashes de esos commits se registran en la adenda de cierre
posterior y en el consenso (un commit no puede contener su propio hash).
No se han editado política, matcher, citas, corpus ni harness CNN en esta rama.
Las correcciones MCP de 5A ya están en sus commits anteriores.

Aceptación privada: **128 casos** (80 reales + 48 sintéticos),
**82805 bytes**, SHA-256
`b8482511783a4d970693c650cd7046274303732643c13f95fdf03de9c9ae6a05`.
Desarrollo: 96 casos (48 reales + 48 sintéticos), disjuntos. Selector determinista
con seed 20261018 y regeneración idéntica por SHA-256. La lista de aceptación se
escribió directamente fuera de Git; no se mostró su contenido ni se ejecutaron
sus casos. Un refinamiento previo al commit hizo explícita la condición de calidad
visible del oráculo ZWARN; no cambió la selección ni usó resultados. Solo el hash
anteriormente indicado en este párrafo identifica la lista final congelada.

Se verificaron 84.759 elegibles y su unión disjunta de splits, 2.114/333/312 en la
cola y 150 históricos/4 objetos demo excluidos. Se excluyó además 1 ID de cola
previamente visible. Reserva disponible: 2.113 train CNN y 333 validación CNN.
Todos los reales elegidos quedan fuera de train/validación histórica de v2.1;
su exposición CNN está declarada por objeto. La reserva **no** es un test
independiente de precisión de ningún predictor. No se usó test 4B ni los 150
históricos para ajustar. La aceptación científica/LLM sigue pendiente para 5C.

La guarda del derivado histórico se mantiene: 4387dd3 coincide 25/25 con
frozen.json, el HEAD actual difiere en 8; ExperimentData rechaza batch4a-v1.
La futura comprobación CNN usará el camino histórico aislado y verificado,
solo con los 48 reales de desarrollo, declarando selección previa en validación.

Pruebas de protocolo: 6 en FM 3.9, 6 en FM 3.12 y 6 en Copilot 3.12. Incluyen
selección determinista/disjunta, preservación de destinos privados, tokens exactos,
ID–etiqueta, respuesta esperada, NPZ y nombre de archivo, fugas en árbol/diff/inputs,
no divulgación y fallo cerrado. Suites completas de las correcciones 5A arriba.
La aceptación no fue una entrada de estas pruebas: solo fixtures inventadas.
Integración completa posterior: **136 FM en 3.9, 136 FM en 3.12 y 121 Copilot
en 3.12**, sin omisiones. La ampliación final del chequeo de staging se validó
repitiendo las seis pruebas de custodia en los tres entornos.
Comprobación de filtraciones previa al staging: cero violaciones en 2.188
superficies; se exige otra comprobación del contenido staged antes del commit.
Inventario final: 1.174 archivos idénticos por SHA-256/tamaño al inventario 5A,
sin extras en los tres árboles inmutables. CSV previo intacto y sin versionar.
Evidencia ligera: [batch5b-freeze.json](evidence/batch5b-freeze.json) y
[compromiso](evidence/batch5b-commitment.json).

### Matriz actualizada H-01–H-18 al congelar 5B-1

| Hallazgo | Estado actual y siguiente límite |
|---|---|
| H-01 | Corrección documental 5A hecha; conclusión condicionada a checkpoints seleccionados. |
| H-02 | Superficies locales corregidas en 5A; publicación pendiente y no autorizada. |
| H-03 | Concurrencia 5A preservada; R5A-01 corregido y O-1 cerrado por comportamiento/mutaciones. |
| H-04 | Wheels vigentes e instalación limpia pendientes de 5C. |
| H-05 | Localidad por TARGETID documentada; independencia física sin establecer. |
| H-06 | Regresiones 5A y O-1 verificadas; no reentrenamiento ni cambio del experimento. |
| H-07 | Preservación final por hash verificada; portable 5C pendiente; no hay respaldo independiente verificado. |
| H-08 | Cronología histórica acotada; protocolo 5B commiteado antes de implementar 5B-2. |
| H-09 | Protocolo y reserva del agente congelados, exposición declarada; no test independiente de precisión. |
| H-10 | Sensibilidad B-101 documentada en 5A; no nueva selección. |
| H-11 | No comparabilidad de cifras históricas/CNN visible; sin afirmación de superioridad v2.1/CNN. |
| H-12 | Reproducción histórica acotada; portabilidad pendiente 5C. |
| H-13 | R5A-02 cerrado; conteos fijos retirados en las tres superficies actuales. |
| H-14 | Persistencia/fallos del evaluador de 5A conservados. |
| H-15 | Contrato v3 y guardas intactos; histórico batch4a-v1 no adoptado como v3. |
| H-16 | Agotamiento explícito de 5A conservado; nueva política pendiente 5B-2. |
| H-17 | Alcance de verificaciones documentado; este cierre requiere revisión independiente. |
| H-18 | Explicación personal de Julian pendiente; ninguna respuesta atribuida. |

**Punto de control:** verificar independientemente ambos commits de congelado,
las regresiones/mutaciones, la custodia y la rúbrica sin abrir aceptación. Solo
después iniciar 5B-2 desde estas ramas: protección model_z y separación de
alternativas, matcher B7/B9 bajo este protocolo, citas y harness CNN en desarrollo.
No ejecutar aceptación ni llamadas pagas sin la autorización de 5C. No publicar.
Respaldo: **no hay respaldo independiente verificado**. Rotación: **sin verificar**.


### Registro de cierre 5B-1 y commits de congelado

| Repositorio | Rama exacta | HEAD corregido de 5A | Primer commit propio: congelado |
|---|---|---|---|
| FM | codex/lote-5b | c99ec856f968f2965a4b6ebd73c399fe2ecb107c | 2b94b3c9544e8d3b6675648785bed359350a74c1 |
| Copilot | codex/lote-5b | 9c5cf0e232736a7a0ce386a487d218517a59de9c | ed9bedc1efbc937cb179200cdb3f91fdbc2b6b4b |

Se comprobó que cada commit de congelado tiene como padre directo su HEAD 5A
corregido. Este registro posterior añade únicamente hashes y handoff; no altera
el protocolo congelado ni implementa 5B-2. Los scripts/protocolo/manifiestos son
idénticos en ambos repositorios. La matriz H-01–H-18 actualizada está arriba.

Después del primer congelado se añadió una regresión sintética que detectó que
una ruta con ID y etiqueta ocultaba el ID pero podía mostrar la etiqueta. Se
corrigió únicamente la redacción de rutas del comprobador: FM `8e723153afe3449b6b19df40dedf8d7a1d7c1e8a`,
Copilot `4942f90045d1d9b05f9abd8e601447be94db0a79`. La prueba falló antes (1 fallo, 5 aprobadas) y las
6 aprobaron después en los tres entornos. No se detectó ninguna filtración real;
no cambian protocolo, población, selección, manifiestos ni hash de aceptación.
Chequeo posterior: 2.248 superficies y cero violaciones. La revisión independiente
debe incluir estos commits posteriores, además del primer congelado.

Estado separado: **R5A-01 cerrado; R5A-02 cerrado; O-1 brecha cerrada;
congelado completado localmente**. Antes de commitear: chequeo de árbol, diff,
staging e inputs visibles: **2.216 superficies, cero filtraciones**; fixtures
plantadas detectadas sin imprimir secretos de custodia. Repetición final de las
6 pruebas del comprobador tras ampliar staging: aprobada en los tres entornos.
Inventario final contra 5A: 1.174 archivos sin cambios de SHA-256/tamaño.
No se añadieron secretos, pesos, datasets, CSV históricos ni logs voluminosos.

SHA-256 de la aceptación final: `b8482511783a4d970693c650cd7046274303732643c13f95fdf03de9c9ae6a05`;
82805 bytes, 128 casos (80 reales, 48 sintéticos), sin abrir contenidos
ni ejecutar casos. Evidencia: [batch5b-close.json](evidence/batch5b-close.json).
**Respaldo independiente: no hay respaldo independiente verificado.**
**Rotación de claves: sin verificar.** **H-18: explicación personal de Julian
pendiente.** Nada de 5B-2 iniciado; ninguna publicación ni llamada paga.

Siguiente paso exacto: revisión independiente de los commits de congelado, su
refuerzo posterior de custodia y sus bases, R5A/O-1, rúbrica y comprobador,
sin abrir aceptación. Tras esa revisión,
5B-2 implementará exclusivamente sobre desarrollo protección de model_z,
alternativas, matcher B7/B9, citas y harness CNN-17 según BATCH_5B_PROTOCOL.md.
Aceptación real/LLM autorizado, paquetes, instalación y cierre quedan en 5C.


## Sesión 5B-1.1 — correcciones de custodia (2026-10-19)

**Correcciones locales completadas; requieren verificación independiente antes
de 5B-2.** Continúan las ramas exactas `codex/lote-5b` de ambos repositorios,
desde FM `f651e7d6141bb6a151bc707ce37ee9a89420e9ce` y Copilot `2915c3a5a6fdc9eea863afaa6b6d5c99be90c0c8`.
Estado inicial conforme: Copilot limpio; FM conserva solo el CSV histórico sin
versionar. Las revisiones de Codex (§13.3 del consenso) y Claude reportada por
Julian se contrastaron con código y reproducciones CLI usando datos inventados.
No hubo exposición real detectada; no se cambió la selección para eludir controles.

| Ticket | Corrección y verificación | FM | Copilot |
|---|---|---|---|
| T1 | Helpers de visibilidad v1 incorporados al selector; sin dependencia del detector mutable. Importación aislada probada y regeneración idéntica. | `bb95c2ab23fd59bc7d893feca40910cd31ad01f3` | `2709252c4a23536df75d2be90775d4fb47b75e79` |
| R5B1-01 / T2 | Fronteras de puntuación, IDs completos y redacción de todos los IDs/etiquetas en rutas. CLI cubre guiones, guiones bajos, separadores, dos IDs y sufijo del case_id; controles alfanuméricos, número largo y redshift aislado. | `e0dff5910cff27cac01aa653313c9a87fa20b12e` | `9cbdf6b8941ae96579727afd67eb374fc9a75fee` |
| R5B1-02 / T3 | Lector común para archivos/blobs y metadata NPZ; índice, blobs añadidos/modificados de todo el rango y mensajes de commit. Fallo cerrado ante lectura imposible. Regresiones staging limpio, commit/borrado, commit vacío y archivos corruptos. | mismo commit de custodia | mismo commit de custodia |
| N-1 / T4 | Regla estática para referencias al generador con rol reservado, incluidos alias, argumento nombrado, variable, concatenación y getattr. Solo las dos rutas expresamente permitidas quedan exceptuadas. Adenda identificada sobre recetas públicas. | mismo commit de custodia | mismo commit de custodia |
| N-2 / T5 | `internal_error` escribe únicamente tipo de excepción saneado en stderr; no mensaje, ruta ni traceback. Payload MCP intacto. Pruebas directas y stdio real. | no aplica al servidor | `ac737dd2e5dc6e73e77a6c65cb53e46a31c7be8a` |

### Reproducibilidad, exposición y límites de interpretación

La regeneración con el comando registrado, cambiando solo destinos, produjo
archivos con hashes idénticos. Directorio temporal nuevo 0700, archivo privado
0600, copia borrada al comparar. No se mostraron IDs, etiquetas ni respuestas:

- Aceptación: `b8482511783a4d970693c650cd7046274303732643c13f95fdf03de9c9ae6a05` (82.805 bytes, 128 casos).
- Desarrollo: `60b2b4584e5a57030a4ff82a1b13d23065505a4d8bb878a20f5d4caecbe3f7c4`.
- Compromiso: `2075bc6d1316203c8043a6bdf73ad0d9c08329c3f4e528d6e71229c77f16ce99`.

Informe T1 sobre las mismas 299 superficies base y 2.759 IDs de cola:
**visibles v1 = 1; detector corregido = 1; adicionales = 0; retirados = 0;
adicionales ∩ desarrollo = 0; adicionales ∩ aceptación = 0; visibles corregidos
∩ aceptación = 0**. Solo se emitieron recuentos. Se mantuvieron población,
selección, etiquetas/oráculos, manifiesto, rúbrica, criterios y compromiso.
El protocolo anterior permanece byte a byte como prefijo, seguido de su adenda.

Los **48 sintéticos de aceptación son derivables del código público**. En 5C
se informarán como comprobaciones de mecanismo con recetas públicas, separados
de los casos reales; no como aceptación ciega. 5B-2 solo puede usar
`synthetic('development')`. La regla estática no promete impedir ofuscación
intencional. No se ejecutaron casos de aceptación ni se inspeccionaron sus
contenidos mediante salida al LLM. Esta reserva tampoco es un test independiente
de precisión del predictor.

### Pruebas, preservación y continuidad

Regresiones por CLI antes de corregir: **17 fallan, 9 pasan**; después, las
**26 pasan**. Diagnóstico N-2: regresión roja antes y 13 pruebas MCP aprobadas
después, con stdio real. Mutaciones en copias privadas: **5/5 detectadas**
(v1, sin índice, sin blobs históricos, sin mensajes y sin regla N-1); baseline
26 aprobadas. Script reproducible: `scripts/check_batch5b11_mutations.py`.
Suites completas: **FM 156 en Python 3.9.6, FM 156 en 3.12.13 y Copilot
142 en 3.12.13**, sin omisiones. Advertencias preexistentes; imports `__file__`
comprobados desde los checkouts; TMPDIR corto, cachés privadas y modo offline.
No se modificaron entornos. `git diff --check` aprobado.

Comprobador corregido sobre todos los argumentos registrados y logs nuevos:
**3.025 superficies, 0 violaciones**; repetición con correcciones en staging:
**3.070 superficies, 0 violaciones**. Los conteos son superficies inspeccionadas,
no casos evaluados. Se preservan logs privados con hashes en
[batch5b11-corrections.json](evidence/batch5b11-corrections.json).
Inventarios inicial/final contra 5A: **1.174 archivos idénticos por SHA-256 y
tamaño**, sin extras en los tres árboles inmutables. CSV histórico intacto y
fuera de Git; no entran pesos, datos, secretos ni logs voluminosos.

Estado separado: **R5B1-01 cerrado; R5B1-02 cerrado; N-1 corregido con límite
público explícito; N-2 implementado; reproducibilidad del compromiso verificada**.
**Respaldo: no hay respaldo independiente verificado. Rotación de claves:
sin verificar. H-18: explicación personal de Julian pendiente.**
Sin llamadas pagas, descargas, inferencia sobre test 4B, cambios científicos,
push, merge, publicación ni despliegue. No se implementaron política, matcher,
citas ni harness CNN; **5B-2 no iniciada**.

**Siguiente paso exacto:** verificación independiente de 5B-1.1, incluyendo
regeneración por hashes, fronteras/redacción, blobs/mensajes, regla N-1,
diagnóstico stderr y preservación. Solo después corresponde iniciar 5B-2 sobre
desarrollo bajo el protocolo y su adenda. No abrir ni evaluar aceptación.


## 5B-2 — requisito de custodia previo a T1 (2026-10-19)

La revisión independiente de Claude sobre FM beedd100 / Copilot f13dacea habilita 5B-2 con dos residuales P3. Se prohíbe acceso ejecutable al selector/generador desde consumidores (incluido desarrollo y roles calculados); desarrollo se lee del JSON congelado. Las IDs numéricas se detectan con frontera de dígitos, incluyendo prefijos alfabéticos, sin marcar números más largos. Se conservan las dos rutas permitidas.

Regresiones CLI con datos inventados: 12 fallos sobre el comprobador previo; 38 aprobadas después. Incluyen for, comprensión, parametrize, tupla, diccionario, import sin uso, y frontera numérica en árbol, índice e historial. El primer ensayo falló por importar el wheel antiguo; se corrigió PYTHONPATH y no se contabiliza como detección. Se acotó un falso positivo de la regla sobre flags booleanos args.synthetic ajenos al selector. Regeneración por SHA-256 idéntica para aceptación, desarrollo y compromiso; copia privada temporal borrada sin mostrar contenidos. No cambian protocolo ni selección. Evidencia: `evidence/batch5b2-custody.json`. Esto no es T1 ni aceptación del agente.


### T2.1 — línea base del matcher congelado

Código Copilot `ed9bedc1efbc937cb179200cdb3f91fdbc2b6b4b` importado desde checkout aislado; parser FM idéntico al congelado. Desarrollo: 96 solicitados, 90 medidos y 6 rechazos de soporte inválido; 78 referencias con 1.560 controles erróneos, sin faltantes. AUROC pareada 0,7484, TPR 0,5385, FPR por candidato 0,1199 y alguna falsa confirmación en 0,6667 de objetos con controles. Ruido: 9/120 sondas positivas, 5/6 objetos con alguna. Bootstrap de objetos (2.000, seed congelada) y todos los estratos/denominadores en `evidence/batch5b2-matcher-baseline.json`. **La puerta congelada falla**; se retirará el veredicto y se conservarán mediciones descriptivas. No se buscará otro umbral.

La observación histórica 20/139 frente a 17,5% procedía de un único control y no establece por sí sola una tasa general de falsa confirmación; no se reprodujo ni se usó para ajustar. La línea base nueva usa exclusivamente desarrollo. Esto no mide exactitud comparativa CNN/v2.1 ni comportamiento de un LLM real.


### T1 — política explicativa protegida por código

El ejecutor obtiene la predicción antes de consultar al LLM; conserva el número canónico, identidad y contrato. `submit_report` solo admite IDs de observaciones registradas y una valoración conservadora; no admite redshift, cantidades, herramientas ni prosa. Las explicaciones publicables se renderizan de esas observaciones mediante plantillas deterministas. La prosa libre del LLM queda en la traza como borrador no validado, causa explicación incompleta y no se publica como conclusión. No se afirma que una regla textual entienda contradicciones semánticas.

Estados distintos: completo, entrada inválida, datos insuficientes, ambigüedad, explicación incompleta y fallo técnico. Una abstención o fallo posterior conserva toda predicción oficial válida; sin ella model_z es null. CLI, salida estructurada y evaluador aplican la política; el evaluador v3 rechaza sustituciones y no adopta corridas históricas. Su columna histórica z_final proyecta model_z; confidence=not_applicable, no una confianza inventada. Los CSV históricos no cambian.

66 regresiones pertinentes aprobadas, incluidas simulaciones del SDK con HTTP local: sobrescritura, mediciones/prosa incompatibles, herramienta/observación inventada, presupuesto, informe ausente, error técnico posterior, entrada inválida frente a activo ausente, persistencia y CLI. Son pruebas de contratos de software; la conducta de un LLM real queda sin validar. La conservación de model_z no es una mejora de precisión del LLM. Citas y matcher continúan en T3/T2; T1 no los da por terminados.


### 5B-2 T2 — mediciones descriptivas (implementación)

La puerta de T2.1 falló y se retira `verdict`; la salida declara
`physical_confirmation=false`. El catálogo histórico queda idéntico, sin
correcciones aire/vacío. El SNR de píxel es `(flux - mediana local de 51 píxeles)
* sqrt(ivar)`, con signo para emisión/absorción y detección fija SNR≥5. No propaga
incertidumbre del continuo, covarianza ni resolución instrumental. IVAR ausente
sigue siendo uno por contrato; no se estima una varianza para rescatar ejemplos.

Las regiones se separan por mask, IVAR inválida y saltos de coordenadas según la
regla de soporte v3. Cada línea requiere ventana completa de max(12 Å, dos pasos
locales). Ca H/K usa absorción; las demás líneas del catálogo usan emisión.
Modalidades no soportadas y líneas fuera de soporte no se tratan como refutación.
Cada pico y candidato incluye procedencia; `lambda_observada/lambda_reposo−1` se
calcula en código y todas las interpretaciones usan la misma comparación. Una
línea con varias interpretaciones queda ambigua, sin sustituir model_z.

54 regresiones de mecanismos/interfaces pasan con datos locales; incluyen ruido,
z erróneo, fuera de cobertura, huecos por tres mecanismos, mask/ivar, inversión,
permutación, absorción y cuatro interpretaciones de una línea. El ejemplo
histórico trap_single_line carece de IVAR medida y no supera SNR≥5 con el valor
por defecto; se conserva ese resultado. Medición terminada en código 01bed86: 96 solicitados, 90 medidos, seis entradas
inválidas, 78 referencias con 1.560 controles sin faltantes. AUROC pareada 0,77147;
TPR 0,21795; FPR por candidato 0,00128; alguna falsa señal por objeto 0,02564.
Ruido 0/120 cruces de umbral en seis objetos. Líneas inyectadas visibles: 74/102
recuperadas, cero falsos matches en 270 posiciones. Las 12 grillas reordenadas
coinciden exactamente. Puerta **FALLA por TPR**. Un cruce del umbral 0,4 aquí es
un diagnóstico del score, nunca un veredicto publicado. No se prueba otro umbral.
`docs/evidence/batch5b2-matcher-descriptive.json` contiene estratos, controles,
IC bootstrap de 2.000 réplicas por objeto y hashes de trazas privadas.

Después de medir se agregó exclusivamente la guarda de desbordamiento para
hipótesis finitas extremas (p. ej., z=1e308): devuelve longitud nula y soporte
fuera del dominio numérico. Ningún z medido activa esa rama; la regresión prueba
serialización JSON finita. T2 queda implementado y medido en desarrollo; el
comportamiento del LLM y la aceptación siguen pendientes de 5C.

### 5B-2 T3 — citas y revisión separadas

Cada recuperación devuelve corpus_revision, recurso y SHA-256, texto íntegro,
fragmento con offsets de caracteres y hash. El ejecutor coteja el contenido con
el corpus y solo publica citas de IDs reales recuperados en observaciones
seleccionadas. submit_report no recibe afirmaciones libres ni texto atribuido;
renderiza extractos exactos con su procedencia y una limitación explícita sobre
predicciones individuales. El contenido del corpus no se modifica; las notas son
editoriales locales y las entradas de catálogo no tienen bibliografía externa
por entrada. No se confunde su hash con veracidad científica.

Se comprobaron todos los ejemplos de cita del prompt contra el corpus:
Halpha_6563 sí existe; solo se permite tras recuperarlo. 52 pruebas pasan,
incluidos ID inexistente/no recuperado, fuente/texto/hash alterado y separación
entre ID válido, respaldo textual y ciencia. `copilot.review` registra juicios
independientes, soporte por par afirmación–cita, discrepancias/adjudicación y
fallos por afirmaciones sin respaldo; no usa regex como evaluación semántica.
`BATCH_5C_REVIEW.md` prepara la rúbrica sin cambiar el protocolo. La revisión
semántica real y sus resultados permanecen pendientes de 5C.
