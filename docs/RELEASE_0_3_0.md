# Release local 0.3.0 — borrador, sin publicar

Ambos paquetes pasan de 0.2.0 a 0.3.0 porque los wheels 0.2.0 archivados solo representaban el lote 2. Esta entrega incorpora el contrato de entrada v3 y las correcciones posteriores ya presentes en las fuentes, junto con las herramientas/ejecutor de 5C. Copilot requiere desi-fm >=0.3.0,<0.4 para evitar mezclar contratos. No cambia el checkpoint predeterminado v2.1; CNN-17 sigue experimental. No hay entrenamiento ni selección nueva.

FM agrega un demo Gradio local instalable y opcional (extra ui), sin depender del hosting ZeroGPU. Copilot agrega desarrollo exclusivo de manifiesto, esfuerzo autorizado y contabilidad sellada por fase, bootstrap predict+identify, huella SDK beta y verificación de wheels instalados. La CLI individual no habilita gasto; la evaluación paga usa la campaña registrada.

La versión del paquete identifica software, no una aprobación científica. Piloto, aceptación, revisión semántica y publicación tienen estados separados en BATCH_5C_REPORT.md. Publicación no autorizada.

Estado del experimento: piloto interrumpido por fallo de integración en la primera
llamada, sin evidencia de comportamiento ni respuesta utilizable;
las otras 23 filas quedaron pendientes. No se eligió variante ni se abrió
aceptación. No hay aprobación científica. Build-05/installed-env conserva el
paquete evaluado; build-06/release-env entrega los cambios posteriores de revisión
y puntuación, con llm_path idéntico por variante. Versiones y hashes concretos
en evidence/batch5c-delivery.json; el número 0.3.0 solo no distingue esos wheels.

Revisión/adjudicación IA: no habilitada para uso real por dos P2 abiertos de D-r2.
La entrega conserva ese estado identificado; ver BATCH_5C_REMAINING.md.
