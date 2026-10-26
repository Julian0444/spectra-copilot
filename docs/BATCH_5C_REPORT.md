# Lote 5C — ejecución local en curso

Fuente canónica por resultado: este informe describe implementación; evidencia de pruebas en `evidence/batch5c-a.json`; registro experimental todavía pendiente. Los registros privados completos están en lote-5c-20261025-f50jj9q_. No se abrió aceptación ni se hicieron llamadas pagas.

## Hito A

5B-2.2: verificación independiente del 2026-10-23 registrada sin repetirla (consenso §13.11; evidence/batch5c-prior-review.json). Modelo/esfuerzo históricos exactos no registrados.

Cambios de comportamiento: predict seguido de identify al inicio (2 de 6 análisis), ambas observaciones al mensaje inicial; esfuerzo low/medium transmitido y comparado por guarda; lectura única de bytes verificados y plazo absoluto del padre; modo development acotado al registro de 12 inputs, con 24 filas y esfuerzo por fila; campañas de un intento por fase, sin transferencias ni continuación con gasto desconocido. CLI individual queda sin gasto; las fases pagas usan copilot.acceptance. La identidad installed-5c exigida se implementa/comprueba en B antes del piloto.

Cambios de verificación/documentación: regresiones del float y del umbral 100000 en el worker real; SDK beta messages incluido en huella; 48 reales + 42 sintéticos válidos aclarados; configuración vigente primero; aislamiento ANTHROPIC_BASE_URL en el conteo.

Diseño A-6: Opus 5.5 propuso independientemente y luego criticó la propuesta Codex en clones f153283/7d6bfdb y 7f0b5fb/8a3a503. Rematerializó 12/12 inputs idénticos. Sus propuestas de cambiar regla/puerta fueron retiradas; rigen las de Julian. Primero elegir, después aplicar puerta; índice de pares desde cero. Proyección de camino LLM y riesgo de POST interrumpido se fijan en 5C-1. Sus dos rondas son diseño, no revisión final de implementación ni revisión semántica.

La campaña y registro se comprometen en docs/protocol/batch5c-campaign.json y batch5c-development-registry.json, ambos hasheados por identidad. La ruta de campaña tiene compromiso SHA para evitar cambiarla al recapturar identidad en D. Un operador puede alterar un protocolo: esto no se presenta como aislamiento frente a un operador hostil.

El materializador empaquetado `python -m copilot.development` rederiva únicamente desarrollo desde el manifiesto 60b2b458… y datos locales verificados; nunca abre aceptación ni ejecuta modelos. La primera materialización nueva detectó un error del registrador: el contrato rechazaba el caso inválido antes de registrarlo. Se corrigió el digest de arrays para incluirlo sin declararlo válido. Se conservaron ambos intentos de preparación; cero pagos.

## Pendientes

Revisión final A; wheels/instalación B; piloto C; puerta y aceptación D–E condicionadas; demo/documentación/release local F–G. v2.1 por defecto; CNN-17 experimental; model_z oficial. Mantener visible 139/150 frente a 119/150; no prueba superioridad ni independencia física.

Clave: no rotada, por decisión de Julian; vence 2026-11-20. Respaldo independiente, H-18 y adjudicación humana siguen pendientes. Sin push, merge, publicación o despliegue.
