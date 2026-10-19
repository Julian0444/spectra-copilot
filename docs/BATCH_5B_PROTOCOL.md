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
