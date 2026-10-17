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

### Matriz H-01–H-18

| Hallazgo | Acción | Fase | Estado | Evidencia |
|---|---|---|---|---|
| H-01 conclusión | Acotar a pares seleccionados; sensibilidades posteriores | 5A A | Hecho | batch5a-analysis.md/json; BATCH_4B.md |
| H-02 superficies | Retirar imagen del recorrido; 12% histórico; hechos del prompt | 5A A | Hecho local | README/model card/report/MCP; publicación pendiente |
| H-03 concurrencia | Hilos FAISS, estado cacheado y stdio | 5A E | Hecho | batch5a-E.json; stdio concurrente |
| H-04 wheels | Rotular 0.2.0 como lote 2; nuevas versiones/instalación | 5A A / 5C | Texto hecho; paquete pendiente | README; BATCH_2.md |
| H-05 localidad | TARGETID/brick; no afirmar independencia física | 5A A | Hecho | batch5a-analysis.json; fuentes oficiales abajo |
| H-06 cobertura | Pérdidas/gradientes, normalización, métricas/guardas y mutaciones | 5A B | Hecho | batch5a-B.json; pruebas de gradiente/guardas y 18 mutaciones |
| H-07 reproducción | Preservar camino histórico; paquete portable/respaldo | 5A / 5C / externo | Preservación verificada; portable/respaldo pendientes | manifiesto privado; instrucciones abajo |
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
