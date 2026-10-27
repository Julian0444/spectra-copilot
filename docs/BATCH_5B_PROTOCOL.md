# Protocolo congelado de 5B — versión 1 (5B-1, 2026-10-18)

**Objeto:** comportamiento explicativo y operativo de Spectra Copilot. No mide
precisión independiente ni generalización de v2.1 o CNN. Este documento, la
selección, sus pruebas y el compromiso criptográfico preceden a cualquier
implementación de política, matcher, citas o harness CNN de 5B-2. No contiene
resultados de aceptación. 5B-2 requiere verificación independiente de este cierre.

La autorización actual de llamadas pagas es **cero**. No se autoriza aquí una
corrida LLM, un push, merge, publicación, despliegue, reentrenamiento, cambio de
splits/semillas/checkpoints del 4B ni reconstrucción FAISS. v2.1 permanece por
defecto. El resultado histórico del agente **139/150 → 119/150** sigue visible.

## 1. Población, exposición y límites

Comprobación por SQLite en solo lectura, orden `ordinal` tras elegibilidad de
etiqueta y entrada, y listas de IDs de splits; no se leyeron espectros de test.

| Población | Total | CNN train | CNN validación | Test 4B excluido |
|---|---:|---:|---:|---:|
| Snapshot elegible | 84.759 | 64.759 | 10.000 | 10.000 |
| Posiciones elegibles [80.000,82.000) | 2.000 | 1.528 | 472 | 0 |
| Cola [82.000,84.759) | 2.759 | 2.114 | 333 | 312 |

`training_args.json` de v2.1 fija 80.000 train, 2.000 validación y seed 42;
el manifiesto histórico reconstruye exactamente [80.000,82.000). [0,80.000)
fue train de v2.1; [80.000,82.000) fue validación histórica no independiente;
la cola queda fuera de ambas ventanas de v2.1. No se afirma por ello ausencia
de exposición en todo linaje anterior ni independencia espacial/física.
Todo objeto elegible pertenece a algún split 4B: no existe una reserva limpia
para comparar la precisión de ambos predictores dentro de este snapshot.

Elegimos **solo cola**, sin usar etiquetas, confianza, aciertos o predicciones
para ordenar. Excluimos todo test 4B, los 150 de `eval/cases/labels.csv`, todos
los 2.000 históricos y los objetos de demos `examples/*.npz` de ambos repos.
Los cuatro ejemplos reales del generador FM son de la ventana histórica; los
sintéticos anteriores tampoco son nuestras nuevas recetas. También se excluyen
IDs de cola ya visibles en los árboles base y los documentos de contexto.
La fuente de selección es metadata, nunca resultados del test ni de los 150.

Las predicciones históricas v2.1 de `historical-full-01` están disponibles para
lectura diagnóstica, pero **no se usan para seleccionar ni aceptar** este lote.
No se necesita inferencia nueva para verificar su existencia. Se renuncia a
aprovecharlas porque aquí se prioriza la cola sin train/validación de v2.1.

## 2. Selección reproducible y custodia

Fuentes y SHA-256 están en `evidence/batch5b-commitment.json`. Procedimiento
canónico: `scripts/select_batch5b.py`, seed **20261018**, versión `batch5b-v1`.
Ordenar cada población CNN train/validación por SHA-256 UTF-8 de
`batch5b-v1:20261018:real-<rol>:<object_id>`; desempate por ID textual completo.
Tomar primeros **24 por rol para desarrollo** y siguientes **40 por rol para
aceptación**. No buscar otra semilla ni reemplazar casos difíciles. Si falta
población, abortar; una reducción futura exige nueva versión antes de evaluar.
La ponderación 50/50 entre roles sobrerrepresenta validación CNN deliberadamente:
es un banco de comportamiento, no una estimación de la prevalencia del snapshot.

| Conjunto | Reales | Sintéticos | Total |
|---|---:|---:|---:|
| Desarrollo | 48 (24 train CNN + 24 validación CNN) | 48 | 96 |
| Aceptación privada | 80 (40 + 40) | 48 | 128 |

Cada fila declara exposición v2.1/CNN; los sintéticos declaran ninguna. El
manifiesto de desarrollo es `protocol/batch5b-development.json`. Los IDs públicos
de caso son opacos, derivados de SHA-256 con dominios separados; no codifican
z, calidad, clase o resultado. La lista privada contiene también el mapa de ID
científico, etiqueta y respuesta esperada. Los conjuntos son disjuntos por
objeto y por caso. Solo esos 48 reales pueden usarse para desarrollo CNN/matcher.

La lista privada se escribe **directamente** en un directorio nuevo 0700 con
archivo 0600. El selector muestra únicamente SHA-256, bytes y recuentos. En Git
solo entran desarrollo, procedimiento, scripts, pruebas y compromiso. No mirar
la lista, regenerarla para inspeccionarla, exportar sus etiquetas o ejecutar sus
casos en 5B-1/5B-2. La custodia es separación de roles/proceso, no cifrado ni
ceguera criptográfica frente a alguien que ejecute deliberadamente el selector.

Las respuestas esperadas reales son **oráculos relacionales**: conservar
exactamente el `model_z` devuelto por la herramienta, declarar una advertencia
solo si su flag está en evidencia permitida y no convertir el z del catálogo
privado en salida del modelo. ZWARN privado sirve para estratificar; nunca se
exige al agente adivinarlo ni se lo expone como pista. El oráculo de advertencia
es condicional a que una fuente permitida haya divulgado calidad. No se inventa un número que v2.1 todavía no calculó. En sintéticos se
congelan además rechazo, ambigüedad y candidatos aritméticos esperados. La
exactitud de prosa y citas la juzga un revisor independiente con la rúbrica;
el selector no pretende resolverla automáticamente.

Antes del commit y antes de cada corrida futura, `check_batch5b_leaks.py` lee la
lista sin mostrarla y examina árboles versionables completos, nombres/rutas,
diff neto y todos los commits desde la base 5A, más los archivos que recibiría
el LLM. Los ignorados científicos no son entradas de desarrollo; cualquier
NPZ u otro archivo que vaya al LLM debe pasarse explícitamente. Se revisa metadata
Unicode/numérica de NPZ, además de texto. Los inputs LLM incluyen prompts,
schemas, corpus, mensajes, argumentos/resultados y archivos científicos saneados.
Durante una futura aceptación, el runner usará un alias efímero distinto del ID
de custodia; ese mapa también queda privado.

El comprobador busca IDs completos como tokens, pares ID–etiqueta (valores
numéricos equivalentes) y objetos completos de respuesta esperada. No marca un
redshift aislado. Solo emite recuentos y rutas, redactando el ID si está en una
ruta. Salida 1 ante filtración, 2 ante error de lectura/verificación, 0 si pasa;
nunca imprime una excepción ni datos de custodia. Las pruebas plantan fugas en
árbol, commits y mensajes, prueban fronteras de tokens y números aislados, y
comprueban que stdout/stderr no revelan el contenido. Es un control contra fugas
literales; no demuestra ausencia de paráfrasis o memorización semántica.

Comando de selección (rutas locales en el handoff privado; destinos nuevos):

```sh
python scripts/select_batch5b.py \
  --index <sqlite-local> --splits <batch4a-v1> \
  --historical <FM>/docs/evidence/batch3-historical-ids.json \
  --labels <Copilot>/eval/cases/labels.csv \
  --examples <FM>/examples --examples <Copilot>/examples \
  --repository <FM> <HEAD-5A-corregido-FM> \
  --repository <Copilot> <HEAD-5A-corregido-Copilot> \
  --visible <consenso-previo-inmutable> --visible <auditoria> --visible <revision-B7-B9> \
  --private-dir <privado-nuevo> --development <manifiesto-dev-nuevo> \
  --commitment <compromiso-nuevo>
python scripts/check_batch5b_leaks.py --private <privado>/acceptance.json \
  --repository <FM> <HEAD-5A-corregido-FM> \
  --repository <Copilot> <HEAD-5A-corregido-Copilot> \
  --llm-input <Copilot>/copilot --llm-input <inputs-saneados> \
  --llm-input <contexto-visible-y-documentacion>
```

## 3. Escenarios sintéticos, separados de los reales

Ocho familias, seis recetas por familia/rol. El selector fija ID, seed, z
inyectado (cuando existe), posición de pico y SNR. Son metadata/recetas, no un
harness ni una implementación del matcher. El generador de señales será trabajo
5B-2 y deberá seguir estas reglas antes de usar desarrollo:

- Grilla base lineal 2.048 puntos entre 3.600 y 9.800 Å; flujo continuo
  `1 + .05*sin(wavelength/700)`, ruido gaussiano independiente sigma 1 con
  NumPy PCG64 de la seed de cada receta. `ivar=1`, mask inicialmente falsa.
  Para cada línea visible, amplitud SNR y perfil gaussiano sigma 5 Å. SNR por
  réplica: **0, 2, 5, 10, 20, 50**. No usar z para el continuo.
- Emisión: líneas 1215,7; 1549,1; 1908,7; 2798,8; 3727,1; 4861,3;
  4958,9; 5006,8; 6562,8 Å, desplazadas por `(1+z)`. Absorción: restar
  perfiles de Ca K 3933,7 / H 3968,5 Å; no exigir detección de emisión.
- Ruido: solo continuo y ruido, sin z verdadero ni líneas inyectadas.
- Huecos/cobertura: misma emisión; invalidar [5.000,6.000] y [7.000,7.500] Å;
  las réplicas alternan mask, ivar cero y coordenadas ausentes. Reportar soporte.
- Grilla invertida/permutada: mismo cuádruple de emisión; invertir todos los
  arrays o permutarlos conjuntamente con PCG64(seed+1). Equivalencia frente al
  orden base con tolerancia numérica fijada abajo.
- Soporte inválido: alternar toda mask verdadera, toda ivar cero y flujo NaN;
  error de entrada, sin redshift ni confirmación ni vecinos inventados.
- Línea única: una gaussiana en `peak_angstrom`; sin etiqueta z única. Calcular
  todas las interpretaciones no negativas de 1215,7 / 3727,1 / 5006,8 / 6562,8 Å.
  Ninguna diferencia aritmética ni ausencia de otra línea prueba solución única.

Los sintéticos comprueban mecanismos y abstención; no se mezclan con reales para
presentar precisión astronómica. Reportar cada familia y SNR con denominador.
Se permite iterar solo sobre desarrollo. Cualquier modificación de receta o
criterio necesita protocolo v2 y reserva nueva, nunca mirar aceptación para elegir.

## 4. Rúbrica del agente y reglas de aceptación

Unidad primaria: **caso solicitado**, N=128, con tablas separadas para 80 reales
y 48 sintéticos y por exposición CNN/familia. Una respuesta terminada es un
informe estructurado válido dentro de límites, aunque se abstenga correctamente.
Los errores y timeouts permanecen en N; no se sustituyen. En los 122 casos
con soporte válido se exige llamar a predict y conservar su salida; omitir esa
llamada o fallar por activos cuenta como fallo técnico, aunque haya prosa. Una abstención correcta
es un resultado válido, no un error técnico. Una entrada deliberadamente inválida
pasa solo si devuelve el error correcto sin mediciones inventadas.

| Dimensión | Medición y denominador | Criterio congelado |
|---|---|---|
| Fidelidad a herramientas | Afirmaciones numéricas/categóricas rastreables a resultado y argumento exactos; C herramientas citadas y N casos | 100% fieles, 0 herramientas/mediciones inventadas; métricas por caso y afirmación |
| Conservación model_z | Igualdad del número canónico de predict; nunca reemplazarlo con alternativa; M casos donde predict produjo número válido | 100% de M, 0 sustituciones; reportar M/N y cobertura, no premiar el silencio |
| ID de citas | IDs existentes en corpus fijado / todas las menciones C_id | 100%; una lista vacía no satisface la obligación de citar |
| Respaldo textual | Pares afirmación–cita efectivamente sustentados por fragmento recuperado / C_pair | ≥95%; al menos una cita válida cuando hay afirmación científica externa, ≥95% de informes aplicables |
| Exactitud científica | Afirmaciones correctas con alcance adecuado / todas las afirmaciones científicas C_sci, incluidas sin cita | ≥95%, cero errores críticos; reportar separado del respaldo textual |
| Afirmaciones sin respaldo | Afirmaciones de hecho sin herramienta ni referencia suficiente / C_fact | ≤2%, cero invenciones numéricas; ausencia de confirmación nunca se presenta como refutación |
| Ambigüedad y abstención | Casos de línea única, ruido, soporte inválido, herramientas fallidas; denominador completo A de cada familia aplicable | 100% de casos sintéticos que exigen abstenerse/rechazar; cero soluciones únicas injustificadas |
| Finalización y fallos | Resultados válidos / N=128; estados completos/error/timeout/pending con N explícito | ≥95% (al menos 122/128), ≥95% reales y ≥95% sintéticos; cero fallos silenciosos |
| Latencia | Pared desde solicitud a terminal, incluyendo tools; p50/p95/máximo por estrato, timeouts=120 s | p95 ≤60 s, timeout por caso 120 s; carga fría separada, sin retirarla del total |
| Coste | Tokens input/output/cache, llamadas y coste de todos los intentos con tarifa fijada antes de corrida | Techo propuesto US$12,80 total y media ≤US$0,10 por caso solicitado; consumo desconocido implica coste no certificado |

Errores críticos: alterar model_z, inventar resultados/citas, proclamar certeza
única ante ambigüedad, llamar confianza a probabilidad calibrada, atribuir
independencia a vecinos del mismo encoder, o afirmar superioridad/generalización
del predictor con estos datos. Nunca usar z de catálogo privado para guiar al LLM.
`model_z` es el valor canónico de la tool; formato visual puede redondear pero
el campo estructurado conserva su número. Igualdad de resultados deterministas:
arrays exactos tras ordenar; floats atol 1e-6, rtol 1e-6; valores que la tool
redondea deben coincidir con esa representación, no con un cálculo del LLM.

Anotar afirmaciones atómicas sin duplicarlas por redacción. El revisor recibe
informe, herramientas y fragmentos completos con el sistema oculto, y puntúa
ID, respaldo y ciencia por separado. Un segundo revisor adjudica discrepancias
sin editar respuestas. Guardar ambas puntuaciones, desacuerdos y decisión final.
Si no hay revisor independiente, la exactitud científica queda **sin aceptar**.
Denominador cero = no aplicable, nunca 100%; falta de citas/afirmaciones obligadas
se penaliza en el denominador por caso para impedir éxito por respuesta vacía.
Reportar conteos además de tasas, IC Wilson descriptivo por caso, y no contar
múltiples afirmaciones del mismo objeto como observaciones independientes.

Máximo propuesto: un informe por caso, seis llamadas de análisis, ocho turnos
SDK, un intento sin retry automático. Antes de ejecutar en 5C, Julian debe
autorizar explícitamente proveedor/modelo inmutable o alias fechado, tarifas,
límites de tokens y los techos de arriba. Mientras tanto presupuesto **0**.
Si un modelo no cabe, no reducir muestra a posteriori: solicitar protocolo y
presupuesto revisados sin abrir esta aceptación. Preservar todas las trazas
saneadas y estados, incluso fallidos; registrar versión de fuentes/activos,
hardware, contrato, seed, contexto, consumo y tiempos sin credenciales.

## 5. Matcher B7/B9: protocolo previo a medir

Desarrollo: exclusivamente 48 reales + 48 sintéticos de este manifiesto. No
usar los 150 históricos para umbrales, ejemplos o elección de reglas. Comparar
cotejo en z de referencia (catálogo en reales, inyección en sintéticos cuando
existe) con controles erróneos, **sin llamarlo validación de verdad física**.
Los casos advertidos se conservan y se reportan por separado.

Generar por objeto **20 z erróneos** sin consultar el score: PCG64 con seed
entera de los primeros 16 hex de SHA-256 de
`batch5b-wrong-z:20261019:<case_id>`. Diez uniformes en `log(1+z)` sobre
[0,log(7)], transformados con expm1; rechazar si
`abs(z-z_ref)/(1+z_ref) <= .15`. Otros diez de esa distribución condicionados
al mismo bin de número de líneas esperadas en soporte válido que z_ref:
0, 1, 2, 3–5, ≥6. Máximo 10.000 propuestas por clase. Si no hay diez, reportar
faltantes y denominador real; nunca relajar el criterio ni rellenar duplicados.
En ruido/línea única no existe z_ref único: solo controles de falsa confirmación
y alternativas analíticas. No asignarles una etiqueta única inventada.

Congelar el catálogo en el commit de freeze (`copilot/tools.py`, identidad en
la evidencia). Mantener las longitudes históricas en Å tal como están; no
atribuirles exactitud metrológica ni mezclar correcciones aire/vacío a escondidas.
5B-2 debe declarar en la salida la convención usada y la resolución; si se
corrige el catálogo, requiere nueva versión de protocolo antes de medir y fuentes
verificables. Candidatos B9 calculados solo en código por `λ_obs/λ_rest−1`,
excluyendo z negativo; evaluar todas las interpretaciones con el mismo soporte.

Medir por separado: recall de línea inyectada cuando visible, falsos positivos
por línea y espectro, score de referencia frente a erróneo, AUROC pareada por
objeto, TPR y FPR en el umbral congelado, y cobertura de decisiones. Denominadores:
objetos, líneas verdaderas visibles, todos los controles generados, incluidos
no-match; informar rechazos y controles faltantes. Bootstrap **2.000** réplicas,
seed **20261020**, remuestreando objetos con sus controles agrupados, nunca cada
candidato como objeto independiente. Resultados globales y por familia, SNR,
ZWARN, rol CNN y cobertura (0–.5, .5–.9, .9–.99, ≥.99).

Controles obligatorios: ruido puro en los seis SNR nominales (SNR de línea=0),
cobertura parcial/huecos, mask frente a ivar=0, coordenadas ausentes, inversión
y permutación, absorción, una sola línea con varias interpretaciones y barrido
de múltiples candidatos. Para buscar entre 20 candidatos reportar además tasa
de **alguna** falsa confirmación por espectro; la FPR por candidato no basta.
No-data debe fallar antes de medir. Orden equivalente conserva resultado; datos
inválidos nunca aportan líneas ni cobertura. Las líneas fuera de soporte no
cuentan como ausencias físicas.

No habrá búsqueda abierta de umbrales: evaluar en desarrollo primero el umbral
histórico **0,4** si el score sigue siendo match_fraction. Si cambia la escala,
la única regla candidata será soporte de **dos líneas distintas con SNR≥5**,
residuo en λ ≤max(12 Å, 2 pasos locales de grilla), sin huecos invalidando la
ventana; es regla operativa a contrastar, no ley universal. Una línea nunca
resuelve sola la degeneración. Como puerta para siquiera proponer una etiqueta
de consistencia en aceptación: AUROC ≥0,75, TPR≥0,50, FPR por espectro≤0,05
y cero falsos positivos en ruido sin soporte, con denominadores publicados.
Si falla o faltan controles suficientes, retirar el veredicto y devolver medidas
descriptivas/ambigüedad. No probar otro umbral sobre aceptación ni ajustar
indefinidamente para salvar “confirmación”. Ninguna puerta autoriza corregir z.

## 6. Desarrollo del harness CNN-17, sin test

Usar los **48 reales de desarrollo** ya seleccionados: 24 train CNN y 24
validación CNN. Esta validación intervino en escoger el checkpoint; su desempeño
es descriptivo/operativo y optimista para medir precisión. No usar test, ni
seleccionar otra semilla/paso. CNN-17, paso 6.000, SHA-256
`335b396c3e2ee737a5e62d51851eedb596b42fb815f9a3f4861e42a2cdc9d6f8`,
11.874.874 bytes. v2.1 mantiene sus pesos/servicio y no se sustituye.

La fuente histórica **4387dd36c6ad640f00c6d9fc3bf6448ef3644d50** coincide 25/25
con frozen.json; el HEAD 5A difiere en 8/25. El contrato actual
`batch4-grid-v2:unnormalized-spectra-input-v3` rechaza `batch4a-v1` deliberadamente.
No borrar esa guarda, editar run.json/hashes, cargar el derivado como si fuera
v3 ni pasar por una ruta alternativa que omita la validación. El futuro harness
debe ejecutar el código histórico íntegro en proceso/check-out aislado, verificar
sus 25 fuentes y entorno, y limitar el acceso a IDs train/validación permitidos.
Si el entorno no coincide, detenerse y documentar, sin relajar identidades.

Validación de ingeniería prevista: identidad de checkpoint/config/preprocesado,
shape y finitud, rechazo de entrada mala, paridad con las predicciones de
validación **ya persistidas** para los 24 IDs aplicables (atol/rtol 1e-6), mismo
resultado entre solicitudes, carga fría/caliente, latencia p50/p95 y RSS máximo.
Para train no inventar referencia persistida si falta: comprobar repetibilidad,
no precisión. Tres repeticiones de desarrollo por ID; primer pase separado como
frío, los otros calientes; 4 hilos CPU según entorno fijado, MPS si coincide con
identidad histórica, sincronizando antes de medir. Registrar fallos en 48/48.
Puerta: 100% entradas elegibles procesadas o error tipado explicable, cero mezcla,
paridad aplicable 24/24, ningún cambio de archivos históricos. Latencia/memoria
se reportan, no se usan para elegir otro checkpoint ni para desplegar.

**Esta separación evalúa al agente; no convierte estos objetos en un test
independiente de precisión del predictor.** No publicar diferencias de eta15
CNN/v2.1 como evidencia de superioridad. La evaluación de aceptación y el LLM
real pertenecen a 5C con autorización; 5B-2 solo implementa y comprueba desarrollo.


## Adenda 5B-1.1 (2026-10-19): alcance de custodia y recetas públicas

Esta adenda conserva íntegros población, selección, manifiesto de desarrollo,
rúbrica, criterios y compromiso originales. No autoriza ejecutar aceptación ni
iniciar 5B-2. El SHA-256 de aceptación sigue siendo
`b8482511783a4d970693c650cd7046274303732643c13f95fdf03de9c9ae6a05`.

Las 48 recetas sintéticas de aceptación y sus respuestas esperadas son derivables
del generador público. En 5C sus resultados se informarán por separado como
**comprobaciones de mecanismo con recetas públicas, no como aceptación ciega**.
Esta limitación no cambia denominadores ni umbrales; acota lo que permiten
concluir. La lista de casos reales sigue bajo la custodia documentada.
**5B-2 solo puede usar `synthetic('development')`.** El rol reservado se permite
únicamente dentro de `scripts/select_batch5b.py` y
`tests/test_batch5b_protocol.py`, para selección/reproducibilidad y sus pruebas.
El comprobador marca referencias directas y equivalentes estáticas evidentes
fuera de esas dos rutas exactas, también en blobs y mensajes históricos.
Es una guarda de proceso, no una defensa contra código deliberadamente ofuscado.

La tokenización y lectura v1 usadas para seleccionar quedaron incorporadas al
selector, independientes del detector mutable. Su regeneración debe conservar
los hashes de aceptación, desarrollo y compromiso; cualquier diferencia o nueva
exposición exige registrar una incidencia y detenerse, nunca reseleccionar.
El detector actualizado reconoce IDs completos delimitados por puntuación sin
aceptar subcadenas alfanuméricas, redacta IDs/etiquetas en rutas y lee metadata
NPZ de árbol, índice y blobs añadidos/modificados en el rango. Incluye mensajes
de commit y falla con código 2 ante entradas o blobs ilegibles.


## Adenda 5B-2.2 (2026-10-22): modelo, configuración y recursos autorizados

Julian autorizó para 5B-2.2 migrar el ejecutor a `claude-haiku-5-5` y actualizar
los límites de tokens. Esta adenda se añade conservando el documento anterior
byte a byte. Selección, manifiestos, rúbrica, criterios y umbrales de calidad
permanecen intactos. No inicia 5C ni autoriza gasto.

La [guía oficial de migración](https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide)
identifica `claude-haiku-5-5` como ID fijo, sin sufijo de fecha ni alias separado.
Satisface el requisito de modelo fijado. La [política de versiones](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions)
distingue pesos/configuración fijos del modelo de infraestructura de servicio
que puede cambiar. No se confunde este ID con el alias histórico de Haiku 4.5.

[Tarifas oficiales](https://platform.claude.com/docs/en/about-claude/pricing),
comprobadas el **2026-10-22**, por millón de tokens, entrada/salida:

| Largo del prompt por solicitud | Entrada USD/M | Salida USD/M |
|---|---:|---:|
| Hasta 100.000 tokens inclusive | 0,10 | 0,50 |
| Más de 100.000 tokens | 0,50 | 2,50 |

El ejecutor rechaza antes del POST toda solicitud cuya cota exceda 100.000.
La tarifa alta queda registrada, pero no se utiliza para admitir prompts mayores.
Se conserva la cota de bytes UTF-8 del JSON más **4.096** de framing. El conteo
de desarrollo y su margen se registran en `evidence/batch5b22-tokens.json`;
la cota sigue siendo una hipótesis conservadora de transporte, no una garantía
del proveedor. Un uso liquidado fuera de las cotas queda sin certificar y detiene
la ejecución. No se envía `cache_control`; las categorías de caché deben ser cero.

Configuración fijada **a priori**: `thinking={"type":"adaptive"}` y
`output_config={"effort":"low"}`. Es una elección de recursos para un agente
limitado a herramientas, sin resultados reales del modelo para calibrarla.
Según la [documentación de thinking](https://platform.claude.com/docs/en/build-with-claude/thinking),
el razonamiento, incluso oculto, se factura como salida y consume `max_tokens`.
Por eso se amplía la salida por llamada de 512 a 4.096; no garantiza que alcance
para una respuesta concreta. Se preservan íntegros los bloques de thinking,
incluso vacíos, y el historial enviado solo admite adiciones. Las trazas saneadas
son copias. No se envían sampling, prefill, fallbacks, streaming, herramientas
de servidor, MCP ni edición de contexto. Refusal y max_tokens son terminales
sin reintento y conservan cualquier model_z disponible.

| Recurso por caso | Límite 5B-2.2 |
|---|---:|
| Entrada acumulada | 800.000 tokens |
| Salida acumulada, incluido razonamiento | 32.768 tokens |
| Salida por llamada | 4.096 tokens |
| Turnos / herramientas de análisis | 8 / 6 |
| Intentos / reintentos automáticos | 1 / 0 |
| Tiempo máximo | 120 s |
| Techo monetario por caso / total de 128 | US$0,10 / US$12,80 |

Ocho solicitudes limitadas a 100.000 suman 800.000 de entrada; ocho salidas de
4.096 suman 32.768. Con reservas completas: `800000 × 0.10/10^6 +
32768 × 0.50/10^6 = US$0,096384/caso`; para 128, **US$12,337152**.
Reservas, liquidaciones y suma del ejecutor usan nanodólares enteros, sin
redondear a microdólares. Presupuesto autorizado por defecto: **US$0**.

SDK `anthropic==0.120.2`, dentro de `>=0.120.2,<0.121`, compatible con los campos
elegidos en tool_runner y count_tokens; no cambia el entorno histórico.
En esta sesión solo se permite el [conteo gratuito](https://platform.claude.com/docs/en/build-with-claude/token-counting)
sobre el replay congelado de desarrollo: 48 reales y 48 sintéticos, nunca
aceptación. Es una estimación de entrada con respuestas simuladas; no valida
finalización, herramientas, latencia ni comportamiento real de Haiku 5.5.
El piloto pago sobre desarrollo sigue pendiente de Julian. La candidata nueva
requiere verificación independiente; no es la identidad final instalada de 5C.


---

## Adenda 5C-1 — prerregistro operativo de desarrollo, 2026-10-25

Autorización de Julian: piloto 12 casos × 2 esfuerzos, US$2,40; confirmación
condicionada de los mismos12, una sola vez, US$1,20; aceptación128 una sola vez,
US$12,80. Cada fase conserva su techo, intento y ledger; no hay transferencias.
Esta adenda agrega el piloto y medium; todo el documento anterior se conserva
íntegro como prefijo. No cambia la rúbrica §4, umbrales, selección de aceptación,
splits, modelo predictor, checkpoints ni prompt. v2.1 sigue por defecto,
CNN-17 experimental y model_z es la predicción oficial.

### Variantes, identidades y condiciones previas

Modelo único claude-haiku-5-5, thinking adaptive, esfuerzos low y medium. Son el
único cambio entre variantes: max_tokens4096, prompt, herramientas, tarifas y
límites iguales. Configuraciones e identidades de camino ejecutado están en
`evidence/batch5c-variants.json` (IDs 5c-1-low / 5c-1-medium, config y llm_path SHA).
Ese registro contiene commits y wheels instalados0.3.0. La identidad completa
incluye el hash de este protocolo; para evitar una referencia circular, se
recaptura después de este commit y se registra externamente antes del primer
POST, comprobando que llm_path no cambió. El registro previo queda preservado.
Cada worker verifica la identidad instalada, fuentes, wheels/RECORD y activos.

Tarifas oficiales verificadas 2026-10-25: US$0,10/M entrada y US$0,50/M salida.
Prompt con cota>100.000 se rechaza antes del POST; thinking reenviado entra en la
cota de la solicitud. Límites por caso:8 turnos,6 análisis,800.000 input,
32.768 output incluido thinking,4096 por llamada,120s,US$0,10; sin fallback,
un intento, cero retries automáticos. Cota por caso US$0,096384; por piloto24
US$2,313216, confirmación12 US$1,156608, aceptación128 US$12,337152. Antes de
reclamar fase debe estar financiada toda su cota, dentro del techo autorizado.
Predict+identify iniciales cuentan2/6; quedan4 análisis. submit_report no cuenta.

El reloj120s incluye arranque/imports/verificación. No se inventa un margen
mínimo nuevo antes del POST: puede comenzar cerca del límite. Si el padre lo
interrumpe con reserva en vuelo, el gasto queda no certificado y se bloquea toda
nueva llamada paga de la campaña. Un resultado negativo así es válido; no se
repite ni sustituye. La clave está no rotada, por decisión de Julian; vence
2026-11-20. Solo el proceso autorizado la carga del Llavero anthropic-api-key.

### Selección fija y orden

Manifiesto desarrollo SHA-256
60b2b4584e5a57030a4ff82a1b13d23065505a4d8bb878a20f5d4caecbe3f7c4.
Dos reales CNN train y dos validation: en cada grupo los dos case_id con menor
SHA-256 de los bytes UTF-8 literales del case_id, desempate case_id literal.
Primero train, después validation. Luego familias sintéticas en orden alfabético:
una receta SNR10 de cada una de las8 familias; si no existiera, menor hash según
la misma regla. Las8 tienen exactamente una SNR10. Selección de12,11 válidos y
un soporte inválido. Registro de inputs SHA
60251d98247192c7089fdd954f43212f86b885b44bbbd927e934e655cf9e696f,
selección SHA c8b6c1a15554713fded199277f136f3e583448af9dc65601a7e3d9de2f0ae6c8.

Una corrida de24 filas: por slot desde0, pares low/medium en slots pares y
medium/low en impares. Mismos bytes científicos, inputs hasheados y alias opacos
por fila; etiquetas separadas. `copilot.development` rederiva y valida registro
positivo de pertenencia antes de crear salidas; worker analiza los mismos bytes
verificados. No abre aceptación. Campaña comprometida por id/ruta en
`protocol/batch5c-campaign.json`; no puede sustituirse al recapturar identidad.

### Métricas y elección: primero elegir, después puerta

`copilot.pilot_score` registra por fila estado/completion_code/stop_reason,
turnos/análisis/tools, obligaciones cumplidas/omitidas, tokens reales frente a
cota por POST (thinking incluido), cabecera beta enviada con respuesta aceptada,
latencia, coste/certificación/reservas y conservación de model_z. Obligaciones:
fidelidad de plantilla a todas las observaciones, model_z oficial conservado,
IDs válidos y recuperados/seleccionados, aritmética de alternativas, cautela no
menor que la recomputada con todas las observaciones y abstención requerida por
el oráculo sintético. Son comprobaciones mecánicas; no certifican ciencia.

Gana más informes complete/ambiguous/insufficient_data con todas las obligaciones;
empate → menos max_tokens o refusal; empate → menor coste certificado en
nanodólares; empate → low. Nunca usa exactitud de z ni filtra variantes por pasar
la puerta. No se elige con gasto desconocido. Comparación operativa pequeña, sin
conclusiones generales. `pilot_decision` registra una sola vez elección/sello/
identidad, y el ejecutor exige ese esfuerzo para confirmación y aceptación.

Puerta sobre última corrida con código y esfuerzo finales,11 válidos:≥10 informes
válidos con obligaciones,≤1 max_tokens/refusal, cero explanation_incomplete,
timeout,technical_error,usage_uncertified,reservas o prompt_tier_exceeded. Un
pending o invalid_input sobre input válido falla la puerta. Inválido rechazado
con cero llamadas; model_z conservado donde hay predicción válida; coste
certificado y dentro de techos. Además Opus0 P1/P2 abiertos sobre estado final.
Si falla: no materializar ni abrir aceptación; documentar causa/pregunta y seguirF.
La puerta del piloto no modifica la rúbrica de aceptación.

### Confirmación y congelación del camino LLM

Solo se corrigen defectos demostrados del arnés/integración; no se optimiza prompt
para estos12 ni se trata abstención correcta como bug. Si cambia camino LLM tras
piloto, una confirmación de12 con esfuerzo ya elegido, mismo registro y techo
US$1,20; no tercer piloto. Se registra defecto/reproducción/commits/huellas antes
de reclamar confirmación. La puerta se aplica entonces a esa confirmación.

`llm_path_digest` fija antes del piloto: todas las fuentes desi_fm y, de Copilot,
__init__,acceptance,acceptance_io,acceptance_worker,agent,budget,campaign,
candidate_identity,explanation,rag,report,spectral,tools; además prompt,schemas,
corpus,activos,predictor,contrato,runtime/SDK,configuración,tarifas/límites y endpoint.
Se excluyen solo hashes del protocolo, instalación/commits/wheels, auxiliares y
fuentes de preparación/puntuación/revisión/MCP que no ejecutan la llamada LLM.
La identidad completa sigue registrando TODAS las fuentes: cambios externos a
esa proyección deben declararse y revisarse, aunque no exijan confirmación.
Cambiar solo adenda/commit de documentación no fuerza una llamada innecesaria.
Cualquier otro cambio de configuración necesita decisión de Julian antes de
aceptación. No hay ajustes después de abrirla.


---

### Enmienda previa al primer pago de 5C-1 — 2026-10-25

Se conserva todo el texto anterior y el registro original de variantes. La
condición «comprobando que llm_path no cambió» del registro inicial se sustituye,
**para este piloto aún no iniciado**, por la igualdad con los nuevos valores de
`evidence/batch5c-variants-prepilot.json`. No se sustituye una corrida: campaña
aún no inicializada, cero POST y cero gasto. Se corrigen defectos demostrados
del arnés autorizados en el encargo; no cambian selección, orden, criterios,
rúbrica, puerta, prompt, configuración, límites ni precios. No se elige ningún
valor en función de resultados del LLM.

Cambios de camino ejecutado respecto de build-03:

- `acceptance.py`: únicamente resolver las cinco rutas antes de reclamar intento
  (308fd04 rojo → 3fe2b96 verde). Opus cerró los dos P2 de A en la verificación
  puntual adicional autorizada por Julian.
- `candidate_identity.py`: rechazar un llm_path guardado que no corresponda a la
  proyección recalculada (66110a2 rojo → 4bbf334 verde; 20 pruebas dirigidas).

Cambios fuera de esa proyección: `acceptance_score.py`, `review.py` y
`review_packet.py`, para revisión semántica, omisiones, agrupación y puntuación
externa al sello; se declaran y revisan como D. No cambió otra parte de la
proyección (predictor, corpus, esquemas, SDK, runtime, activos o configuración).

| Esfuerzo | llm_path original | llm_path vigente antes del piloto |
|---|---|---|
| low | `3aa4871d0064afb86d7532f763b799c7a915ac072065a47a0842dfb1f4378c72` | `8d79a71d8152836cc8005e7c16e4d516b00d14978b0b30700efae50e4d501dbb` |
| medium | `719fbb20ad6c4571e5233e5fce2ff2f2c2872e5c97e5144bc7d2a382a3843d14` | `537e07b9e0d9701012f3029305f7519ac563b6c4cec5855fadd86392f29f2235` |

Los wheels de build-05 y sus commits/hashes están en el registro nuevo. Se
instalaron con `--no-compile`; se comprobó ausencia de bytecode en ambos
paquetes y contenido idéntico a las fuentes de construcción. Cada fase usa un
directorio de protocolo congelado y copias privadas de checkpoint/índice con
hashes idénticos, sin modificar los originales. Se recapturan ambas identidades
contra ese directorio después de este commit y se registran externamente en
archivo nuevo antes del primer POST, exigiendo exactamente los valores de esta
tabla. Toda diferencia ulterior se explica antes de ejecutar. No se actualiza
Python, macOS, dependencias ni activos durante la campaña.


### Adenda 5C-1c — repetición única tras reemplazo de credencial

Julian identifica «credencial inválida; clave reemplazada por Julian»; servicio
anthropic-api-key, reemplazo declarado a las 21:14. La consulta count_tokens
única con clave nueva devuelve HTTP200, 4.805 tokens de entrada. La previa
devolvió401. No se hizo generación diagnóstica. El primer piloto permanece
sellado: interrumpido por fallo de integración en primera llamada, sin evidencia
de comportamiento; reserva US$0,0035706 debitada como gastada sin certificar uso.

Se autoriza UNA repetición: pilot-repeat-run y campaign-repeat, selección y
plan idénticos (24 filas,12 casos,low/medium), misma regla5C-1, prompt, límites y
tarifas. Saldo duro para execute_plan: US$2,3964294. El cap nominal histórico
de fase US$2,40 se mantiene; la autorización efectiva es el saldo menor,
registrado en manifest y launcher. Nunca reiniciar directorios anteriores.

Se usa instalación build-07/diagnostic-env: diagnóstico SDK42b8f3c; no cambio
de credencial en código. llm_path low985e74a43f8be5e6cb82bacb40d0ea82681af065dfd02390f7f1f49b0401158d
y medium0a99d9eb135b2f5d3dda23d81b909199233d62e78805a06a5c1e51e43c13aa07.
Las identidades completas se capturan contra esta adenda congelada antes de POST.
La revisión diagnóstica Opus fue interrumpida por la instrucción de cierre
económico; no se atribuye aprobación. Si variante elegida pasa puerta: una sola
reconstrucción final, una sola verificación final Opus y, sinP1/P2, aceptación
única HitoD. Si falla, aceptación cerrada. Los dosP2 deD siguen declarados.
Solo puntuación mecánica: anotación semántica IA queda para otra sesión;
exactitud científica y aceptación global pendientes. Sin otras revisiones Opus.


### Adenda 5C-2 — cierre, aceptación y anotación semántica (2026-10-27)

Esta adenda conserva íntegros los protocolos anteriores y sustituye las
restricciones de alcance del cierre económico por la autorización de Julian
del 2026-10-27. No cambia rúbrica, umbrales, selección, modelos ni regla del
piloto. No habilita pagos hasta completar el registro y la revisión descritos.

La variante es **low**, elegida por la repetición ya aprobada: 11/11 válidos,
puerta operativa superada. Se conserva el primer intento interrumpido, sin
respuesta utilizable ni evidencia de comportamiento; reserva US$0,0035706
debitada. La repetición costó US$0,0280614 certificado; no se ejecuta otro piloto.
Su sello es 31eb1b78e55836ddaa9457aadf3ef7a8dc83ad93f27f736c35ca6db3e8163137,
y su camino LLM low registrado es
985e74a43f8be5e6cb82bacb40d0ea82681af065dfd02390f7f1f49b0401158d.

Correcciones D-r2: resolución de inventario acotada a disputas/adiciones,
preservando ID/texto no disputados y enumerando cambios; extractos como
fidelidad de extracción, no tesis externa ni autopares; referencias limitadas
a las emitidas y a la semilla salvo disputa; desacuerdos separados de forzados
y cambios; hoja de adjudicación sin etiquetas; validación con contexto original;
schema IA por caso en propuesta y hash de unión en el score. El procedimiento
corregido es BATCH_5C_AI_REVIEW.md y el contrato docs/review/INSTRUCTIONS.md.
No se delega adjudicación humana a ningún asistente. C_pair=0 permanece N/A,
con aceptación global pendiente. El registro previo liga sus hashes exactos.

Antes de materializar los 128 casos, se construye e instala desde commits
registrados, se verifican los wheels, RECORD y recursos, y se captura la identidad
completa contra una copia congelada del protocolo. El registro externo nuevo
incluye hashes de wheels, commits fuente, identidad, protocolo, instrucciones,
esquema/ejemplo, cambios frente a build-08 y el dictamen independiente de Opus.
La comparación debe demostrar el mismo llm_path low del piloto. Si difiere,
se detiene antes de aceptación para una decisión de Julian; no se ejecuta
confirmación ni otra llamada paga por iniciativa del coordinador.

Se permiten reconstrucciones necesarias, justificadas y registradas. Una nueva
construcción no autoriza repetir la evaluación. Wheels, instalación e identidad
evaluados se preservan. Wheels de release distintos llevan ambos hashes,
commits y diferencias de contenido; si cambia código ejecutable, no se publica
con el mismo número de versión ni se atribuye la aceptación previa a ese código.

Para preservar la campaña del piloto, la continuación usa un directorio privado
nuevo, comprometido en protocol/batch5c-closure-campaign.json. Copia sin cambiar
los bytes de las reclamaciones, cierres, decisión, assessment y ledger históricos;
conserva sus referencias a sellos e identidades originales. Un inventario de
traslado registra cada hash y la campaña predecesora. Solo el compromiso de la
campaña nueva cambia; el protocolo privado instalado presenta ese compromiso
bajo el nombre esperado protocol/batch5c-campaign.json. No se reinicia ninguna
fase ni se modifica ningún registro canónico anterior. Pilot ya reclamado impide
otro piloto; proposal no reclamado permite la única aceptación autorizada.
El registro externo identifica esta derivación y los dos hashes de compromiso.

Con revisión independiente de delta/identidad sin P1/P2: una aceptación low,
N=128 global, 80 reales y 48 sintéticos, techo US$12,80 y límites 5B-2.2 intactos.
Custodio, vistas separadas, sello y registro externo antes de etiquetas. Todos
los fallos y pendientes permanecen en el denominador. Si hay defecto de corrida,
se conserva y declara, sin repetir. No se transfiere saldo del piloto.

Dos sesiones NUEVAS de anotación, Astra y Opus, distintas del coordinador y del
revisor, reciben paquetes ciegos equivalentes. El revisor se cierra mientras
anotan; máximo tres sesiones activas. Cada anotación se guarda y hashea antes
de mostrar cualquiera al coordinador o a la otra sesión; se registran ambas
antes de abrir etiquetas/puntuación mecánica. Se auditan los hilos. Es revisión
por IA, no humana independiente; Opus y Haiku comparten proveedor. Ceguera
parcial real/sintética y cualquier exposición de identidad se declaran.
La unión validada y los agregados conservan anotaciones originales y producen
un paquete de todas las disputas para Julian, sin adjudicarlas. Exactitud
científica y aceptación global quedan pendientes hasta su adjudicación.

Opus revisa posteriormente agregados, denominadores, sello, identidad, costes y
fidelidad del informe, y la preparación de publicación/afirmaciones públicas.
Máximo dos rondas por hito; bloqueos persistentes se documentan y consultan,
continuando lo independiente. Astra es el único escritor del proyecto; revisores
no acceden a claves ni hacen llamadas pagas de la aplicación.

No se publica sin la palabra PUBLICAR tras presentar el estado y los comandos.
Luego: rama FM revisada, CI verde en commit exacto, fast-forward main, tag y
release; después Copilot igual. No sobrescribir tags/artefactos. Hugging Face
solo textos, distinguiendo software publicado del código actual del Space.
No se sube el paquete de artefactos. H-18, adjudicación, respaldo independiente,
hospedaje y desactivación de claves viejas no se dan por hechos.
