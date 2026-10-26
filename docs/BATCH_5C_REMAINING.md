# Bloqueos conservados al cierre 5C

El procedimiento de revisión y adjudicación no está habilitado para una
evaluación real. D agotó sus dos rondas: Opus cerró los cuatro P1/P2 de R1,
pero halló **dos P2 nuevos** sobre Copilot 0cdc6ea. No se solicitaron ni
ejecutaron rondas adicionales. Build-06 conserva ese código identificado.

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

Por separado, el piloto quedó interrumpido por fallo de integración en la primera
llamada, sin evidencia de comportamiento. Sigue pendiente; ver diagnóstico
condicionado autorizado en BATCH_5C_REPORT.md. La aceptación permanece cerrada.
No existe variante elegida. La reserva US$0,0035706 no es gasto facturado;
conciliación con el proveedor y cualquier decisión sobre un experimento futuro
requieren tratar el intento preservado. No se concede otro piloto implícitamente.

Cierre económico: la repetición eligió low, pero falló la puerta operativa.
Revisión y reconstrucción final en preparación; aceptación sin abrir. La clave inválida
fue reemplazada por Julian y count_tokens nuevo dio200. Semántica otra sesión.
