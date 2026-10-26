# Lote 5C — cierre económico local; aceptación pendiente

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
