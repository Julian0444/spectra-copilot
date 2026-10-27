# Trabajo pendiente del cierre 5C — 2026-10-27

Correcciones locales de D-P2-N1/N2 y P3-N1/N2/N3: rojo 61b1ce9 (16 fallos,
1 control verde), verde 0ae8ef0 (42 pruebas dirigidas). Pendiente la revisión
independiente del delta, adenda 5C-2 e identidad instalada; no se abre aceptación.
No se repite el piloto aprobado ni se cambian criterios. Después de esa puerta:
una corrida de 128 casos, dos anotaciones IA ciegas, unión y puntuación, paquete
para Julian, revisión del informe y preparación de publicación sin push.

Los P3 no incluidos en la corrección solicitada siguen declarados: detección de
identidad parcial en razones; schema/ejemplo opcionales en paquetes genéricos;
validación incompleta de justificaciones N/A y adiciones; discrepancias por IDs
de observación; anotaciones parciales no se unen; Wilson por subconjunto revisado
es interino. La ejecución controlada debe conservar estos límites y no atribuir
al validador comprobaciones que no hace. H-18, adjudicación, respaldo independiente,
hospedaje de artefactos y desactivación de claves viejas requieren acción humana.

## Registro histórico del bloqueo económico


El procedimiento de revisión y adjudicación no está habilitado para una
evaluación real. D agotó sus dos rondas: Opus cerró los cuatro P1/P2 de R1,
pero halló **dos P2 nuevos** sobre Copilot 0cdc6ea. No hubo nuevas rondas de corrección de D. La verificación final única del
cierre económico reprodujo los dos P2 sobre build-08, cuyo código D es idéntico.

Codex reprodujo ambos hallazgos contra los módulos instalados de release-env,
con fixtures inventadas y sin red. No se consumieron etiquetas de aceptación.
Logs privados D2-reproduction-N1.log y D2-reproduction-N2.log. Fuente independiente:
reviews/D-r2/REVIEW.md. Las pruebas verdes existentes no detectaban estos casos.

| Bloqueo | Reproducción | Trabajo requerido antes de usarlo |
|---|---|---|
| D-P2-N1: resolución de inventario sin límite a disputas | Dos revisores acuerdan un error crítico sin disputa; una resolución que omite su afirmación valida y cambia críticos 1→0, sin dejar el ID en el score | Preservar todos los acuerdos no disputados; rechazar cambios fuera de disputas/adiciones registradas; registrar exclusiones/cambios; regresión y verificación independiente |
| D-P2-N2: extractos citados y pares ambiguos | El validador admite tanto el autopar extracto→su ID (C_pair 1/1) como tratarlo como ciencia externa sin par (una cita omitida); también admite una referencia no recuperada en el caso | Especificar y validar el tratamiento de quotation y Retrieved reference IDs conforme a la rúbrica literal; limitar referencias a las emitidas, con disputas explícitas; regresiones y verificación independiente |

Ninguno cambia por sí solo acceptance_status a aprobado; ambos comprometen
métricas congeladas. No se usa ese detalle como excusa para aprobar D.
No se cambian criterios ni se clasifica ciencia para obtener un cierre favorable.

Observaciones P3 conservadas: una unión editada sin schema por caso cae al scorer
heredado; falta hash de la unión en el score; diferencias reales y juicio forzado
por ceguera se mezclan; validación/adjudicación y notas de N/A tienen huecos;
detección de identidad en razones es parcial; schema/ejemplo son opcionales en
algunos paquetes; una sesión parcial no se puede unir; Wilson por caso revisado
es interino si hay pendientes. Hay un desfase documental executor_fallback y
commits de documentación que también incluyeron código. El informe independiente
contiene las ubicaciones y reproducciones; no se ocultan esos límites.

El paquete de adjudicación real no existe porque aceptación no se abrió.
Los schemas/ejemplos presentes son material de preparación, no una autorización
para anotar o puntuar datos reales. Las seis preguntas de H-18 sí quedan listas
en BATCH_5C_HUMAN_ACTIONS.md.

El primer intento se conserva como piloto interrumpido por fallo de integración
en la primera llamada, sin evidencia de comportamiento. La reserva
US$0,0035706 fue debitada como gastada; no certifica facturación real.

Julian reemplazó la credencial inválida; count_tokens nuevo dio 200. La
repetición autorizada terminó y eligió low: 11/11 informes con obligaciones,
puerta operativa superada. Reconstrucción final build-08 y verificación final
única de Opus terminadas. Dictamen: bloqueado para abrir aceptación por N1/N2,
0 P1 y 2 P2; ningún P1/P2 nuevo en el cierre económico. No se abre aceptación
ni se modifica la puerta. Anotación semántica en otra sesión. EF-P3-1, las
frases sobre reconstrucción en preparación, se corrigió documentalmente tras
verificar la evidencia; sin otra revisión ni cambio de código.
