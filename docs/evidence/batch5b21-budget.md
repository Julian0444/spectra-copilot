# 5B-2.1 — factibilidad de reserva, medida offline

Fecha: 2026-10-19. Medición T5; no autorización ni ejecución de 5C.
Reproductor versionado en Copilot: `scripts/measure_batch5b21_budget.py`, commit
`268683a0975988cbccc9cefd2c58f0a8b3376a68`.

Evidencia privada:
`/Users/jirustaroure/.local/state/spectra-consolidation/lote-5b-2-1-20261019-9ax7b98b/budget-development/`.
`rows.json` registra cada solicitud y escenario; `requests/` conserva los cuerpos
HTTP, sin cabeceras ni claves; `summary.json` contiene agregados e identidad.
`T5-development.command.json` y `.log` registran la ejecución. No aceptación.

Se recorrieron los 48 reales y 48 sintéticos del desarrollo congelado:
90 entradas válidas y 6 inválidas, rechazadas antes del SDK. Para cada entrada
válida se serializaron seis conversaciones de 3–8 turnos: 540 conversaciones,
2.970 solicitudes. SDK Anthropic real, transporte `httpx.MockTransport`, sockets
bloqueados, respuestas de tools reales de desarrollo y elecciones de tools
simuladas. Cero intentos de red, llamadas remotas o gasto. Se verificaron los
activos locales contra sus hashes registrados. Se reutilizó cada payload de tool
dentro del mismo caso entre escenarios; la máscara de reconstrucción usa una
semilla local registrada. No entrenamiento ni inferencia sobre test 4B.

Los recorridos de 3–6 turnos añaden líneas, referencia, vecinos, otra hipótesis
de líneas y reconstrucción, terminando en submit; predict inicial cuenta entre
las seis tools analíticas. Los de 7–8 añaden uno/dos errores de argumentos
rechazados por el SDK: representan reparación de argumentos, no reintentos de
red. El transporte simulado serializa también los turnos que el presupuesto
real rechazaría; estos son contrafactuales offline, no una relajación del runner.

## Bytes medidos y tokens supuestos

El cuerpo HTTP coincide en bytes con el JSON usado por `request_bound`.
La reserva de entrada es esos bytes UTF-8 + 4.096. El primer POST ocupa
8.935–8.952 bytes antes de esa adición. El primer resultado completo de líneas
ocupa 4.179–76.512 bytes (mediana 15.847,5); su vista compactada ocupa
2.014–20.433 (mediana 4.353). El ledger completo se conserva.

| Turnos solicitados | POST máximo (bytes) | Completan con uso igual a la cota | Completan suponiendo 2 bytes/token | Completan suponiendo 4 bytes/token |
|---:|---:|---:|---:|---:|
| 3 | 35.708 | 69/90 | 90/90 | 90/90 |
| 4 | 36.474 | 0/90 | 77/90 | 90/90 |
| 5 | 59.447 | 0/90 | 58/90 | 71/90 |
| 6 | 61.115 | 0/90 | 40/90 | 63/90 |
| 7 | 61.413 | 0/90 | 0/90 | 62/90 |
| 8 | 61.711 | 0/90 | 0/90 | 58/90 |

El replay usa el `Budget` vigente: 64.000 entrada, 4.096 salida, 512 salida/POST,
8 llamadas, cero reintentos y US$0,10 autorizado **solo en el simulador**.
El perfil conservador liquida cada entrada por su cota completa y cada salida
por 512. Los otros dos usan `ceil(bytes/divisor)+496` de entrada y el tamaño
simulado de respuesta/divisor de salida. Son sensibilidades ilustrativas,
**no tokenización observada ni garantía del proveedor**. Todos reservan con la
cota vigente antes de liquidar. En los recorridos sin errores de esquema,
21/90 admiten solo dos llamadas y 69/90 tres bajo el perfil conservador.

La evidencia confirma un riesgo de factibilidad, no una tasa de finalización
de un LLM real. Ni siquiera un recorrido de tres turnos ofrece garantía para
todos los payloads. No se ha cambiado la puerta ni se afirma alcanzar su 95%.

## Dos opciones para decisión de Julian

Ambas conservan los techos congelados y requieren implementación y comprobación
posteriores, antes de autorización de 5C. Ninguna se implementó en esta sesión.

1. **Reducir solicitudes manteniendo la cota por bytes.** Compactar schemas,
   instrucciones e historial visible, conservando el ledger completo y todas las
   alternativas/estados mínimos. Un objetivo suficiente para ocho turnos sería
   una cota de entrada de como máximo 8.000 por solicitud (3.904 bytes de cuerpo,
   dada la reserva adicional de 4.096). Es un objetivo exigente, no un resultado
   alcanzado: el primer cuerpo actual ya lo supera. Otra decisión de producto
   sería un recorrido menor, con comprobación explícita de información perdida
   y finalización. Debe repetirse desarrollo y verificar fidelidad/cautela antes
   de considerar aceptación.
2. **Usar una cota de tokens más ajustada y verificable.** Evaluar un contador
   compatible con el modelo y todo el framing/schema, con margen documentado y
   rechazo ante conteo ausente o inválido. Mantener reserva previa, liquidación
   real, detención ante consumo desconocido y todos los techos. La disponibilidad,
   corrección y posible coste de un servicio de conteo quedan por verificar;
   no se ha llamado a ningún servicio ni se supone que sea gratis. Si requiere
   gasto adicional, debe caber en los mismos techos o descartarse.

Con el modelo y tarifas **registrados en 5B-2**, Haiku
`claude-haiku-4-5-20251001`, US$1/M entrada y US$5/M salida, ambas opciones
mantendrían un máximo de generación de
`(64000 + 4096 × 5) / 10^6 = US$0,08448/caso`,
`128 × 0,08448 = US$10,81344` total. Los techos absolutos siguen siendo
US$0,10/caso y US$12,80 total; margen máximo US$0,01552/caso y US$1,98656 global
para cualquier cargo adicional que se autorice y contabilice.
Son tarifas heredadas, no precios actuales verificados. Cambiar modelo exige
recalcular y fijar tarifas antes de autorizar. El presupuesto de producción por
defecto sigue en cero.

**Estado:** medido, dos opciones propuestas, ninguna elegida. Primero revisión
independiente de 5B-2.1; después Julian decide presupuesto y modelo. No iniciar 5C.
