# Reproducción local de 0.3.0

Esta guía usa wheels instalados fuera de los checkouts. No presupone acceso a
Hub, aceptación privada ni una clave. La evidencia experimental vigente está en
[BATCH_5C_REPORT.md](BATCH_5C_REPORT.md); una demo no constituye aceptación.
Los wheels 0.2.0 archivados solo certifican el lote 2.

La instalación actual de diagnóstico y repetición es build-07/diagnostic-env.
Frente a build-06 cambia solo budget.py para registrar fallos SDK. Build-05 y
build-06 se conservan congelados. La demo/CLI/API/MCP/Gradio se comprobaron antes
en build-05/06; no se atribuye una nueva prueba de interfaces a build-07. Esta
última verificó fuentes instaladas, RECORD, identidades y 13 pruebas diagnósticas;
el piloto repetido se ejecutó desde ella. La reconstrucción final build-08/final-env está terminada; véase el apartado final. Nunca ejecutar nuevamente los
lanzadores privados de pago: sus autorizaciones únicas están consumidas.

## Entorno y activos

Comprobado en macOS 26.6.2 arm64, Python 3.12.13: anthropic 0.120.2, numpy 2.5.1,
scipy 1.18.0, torch 2.13.0, pyarrow 25.0.0, httpx 0.28.1, faiss-cpu 1.15.0,
mcp 2.0.0 y pydantic 2.13.4. Versiones completas y hashes de descarga quedan en
`evidence/batch5c-dependencies.txt` y `evidence/batch5c-wheelhouse.json`.
No se ha comprobado esta combinación en Linux/Windows ni otro hardware.

El directorio privado de la corrida contiene `diagnostic-env`, `build-07/wheels`,
`build-07/installed-build.json`, `downloaded-wheels`, `frozen-assets`,
`protocol-pilot/docs`, `development-v2` y registros de comandos. Los paths de ese
manifiesto son locales: al trasladarlo, cambie solo wheel_path a las copias con
el mismo hash, conserve el original y registre un manifiesto nuevo. Toda identidad
completa debe recapturarse; una nueva máquina no hereda aceptación experimental.

Activos verificados, sin descargarlos ni seleccionarlos de nuevo:

| Activo | SHA-256 |
|---|---|
| checkpoint v2.1, paso 30000 | `40247cbe0e706a66084d001b36424081554c26d3eb75c1f8b0ebec89cf5afe5a` |
| spectra.faiss | `fc13007f951e2d1c1dc7e30338f6de4203b65d5c9c44fddc1d39ce4da921968b` |
| spectra_meta.npz | `83e4bdc035328618636b1e86ddad49367df8b2d70dd9ac90a2bb8bd4f503e9ee` |

Para reconstruir, use clones nuevos de los commits fuente del manifiesto y
`pip wheel --no-deps --no-build-isolation`, con las dependencias fijadas. Cada
wheel nuevo se identifica por su hash; timestamps ZIP pueden cambiar ese hash
aun con fuentes iguales. Verifique contenido contra los commits y RECORD,
`direct_url.json` y `module.__file__`; no se valida solo por el nombre 0.3.0.

## Instalación y quick start

Defina rutas absolutas existentes para `S5C_ARCHIVE` (corrida privada), `S5C_CP`
(fuentes Copilot) y `S5C_FM` (fuentes FM). Para crear otro entorno, elija un
directorio nuevo `S5C_ENV`; para usar el comprobado, apunte a release-env.
Este bloque reproduce la instalación offline ya ensayada; no toca el entorno
histórico wheel-env ni instala de forma editable:

```sh
python3.12 -m venv "$S5C_ENV"
"$S5C_ENV/bin/python" -m pip --isolated install --no-index \
  --find-links "$S5C_ARCHIVE/downloaded-wheels" \
  -r "$S5C_ARCHIVE/declared-dependencies.txt" \
  -c "$S5C_ARCHIVE/dependency-constraints.txt"
"$S5C_ENV/bin/python" -m pip --isolated install --no-index --no-deps --no-compile \
  "$S5C_ARCHIVE/build-07/wheels/desi_fm-0.3.0-py3-none-any.whl" \
  "$S5C_ARCHIVE/build-07/wheels/spectra_copilot-0.3.0-py3-none-any.whl"
"$S5C_ENV/bin/python" -m pip check
```

Antes de los siguientes comandos use un cwd privado fuera de ambos repos y
sin PYTHONPATH. El checkpoint y el índice son copias locales verificadas:

```sh
unset PYTHONPATH
export DESI_FM_CKPT="$S5C_ARCHIVE/frozen-assets/checkpoint_last.pt"
export DESI_FM_INDEX_DIR="$S5C_ARCHIVE/frozen-assets"
export HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 GRADIO_ANALYTICS_ENABLED=False
"$S5C_ENV/bin/python" -I -B -m copilot \
  "$S5C_ARCHIVE/development-v2/inputs/input_0000.npz"
"$S5C_ENV/bin/python" -I -B "$S5C_CP/scripts/demo_batch5c.py" \
  --valid "$S5C_ARCHIVE/development-v2/inputs/input_0000.npz" \
  --invalid "$S5C_ARCHIVE/development-v2/inputs/input_0007.npz" \
  --ambiguous "$S5C_ARCHIVE/development-v2/inputs/input_0011.npz" \
  --build-manifest "$S5C_ARCHIVE/build-07/installed-build.json" \
  --output /ruta/privada/nueva/demo.json
```

Resultado comprobado: model_z=1.0745 para input_0000; input_0007 rechazado;
input_0011 devuelve ambiguous; lookup_reference por MCP stdio funciona. Son
inputs de desarrollo, no datos independientes. No se exige igualdad del último
bit entre plataformas. La demo no llama a ningún LLM ni sustituye model_z.

El lector instalado `copilot.development` puede rematerializar los 12 inputs con
el manifiesto desarrollo `60b2b458…`, raw-root e índice SQLite locales explícitos.
La corrida verificó igualdad byte a byte de las materializaciones. No incluye ni
lee aceptación; no se distribuyen datos privados dentro del wheel.

## Gradio, API y MCP

```sh
"$S5C_ENV/bin/python" -I -B -m desi_fm.demo --port 7860
"$S5C_ENV/bin/python" -I -B -m uvicorn desi_fm.api:app --host 127.0.0.1 --port 8000
"$S5C_ENV/bin/python" -I -B -m copilot.mcp_server
```

Ejecute cada servidor por separado. Gradio usa 127.0.0.1 y share=false; requiere
un solo espectro, rechaza soporte inválido y muestra concentración no calibrada.
API: /healthz, /predict (upload), /predict_json y error 422 para entrada inválida.
MCP expone predict_redshift, identify_spectral_lines, reconstruct_spectrum,
find_similar_spectra y lookup_reference. Errores de dominio llevan is_error y
JSON tipado; errores de esquema los valida MCP/Pydantic. Se verificaron las cinco
tools por stdio y recuperación después de error. Gradio se probó mediante su
upload/predict HTTP real y masking 0/0.35; no se atribuye prueba al hosting público.

`check_installed_5c.py`, `check_installed_campaign_5c.py` y
`check_gradio_5c.py` guardan evidencia detallada; use --help y destinos nuevos.
Las pruebas de fuentes con wheel-env viejo están rotuladas aparte y no cuentan
como instalación limpia. Una instalación sin bytecode de proyecto evita leer
.pyc no cubiertos por RECORD; -B por sí solo solo impide escribirlos.

## Experimento pago y preservación

No se repite el piloto ni aceptación mediante esta guía. Los intentos únicos,
presupuestos, credencial en memoria y puertas están en BATCH_5B_PROTOCOL.md y
BATCH_5C_EXECUTION.md. El código de puntuación puede releer salidas selladas sin
pagos, siempre a una ruta nueva. El registro externo del sello debe comprobarse
antes de abrir etiquetas. No se actualizan versiones, protocolo o activos en
medio de una fase.

v2.1 sigue por defecto; CNN-17 experimental. El resultado histórico del agente
es **139/150 frente a 119/150**. No se establece condición de foundation model,
independencia física ni superioridad CNN/v2.1. Un respaldo en otro directorio del
mismo disco no es respaldo independiente. Publicación requiere una acción humana
posterior; estos comandos no publican nada.

## Reconstrucción final única

Build-08/final-env: fuentes CP94a8f44 y FM8514aab, todas las fuentes ejecutables
e idéntico llm_path low respecto al build-07 evaluado. RECORD e identidad
verificados, sin repetir piloto ni cambiar código. Para la instalación final
use final-env y build-08 en lugar de diagnostic-env y build-07 en los comandos
de esta guía. Los entornos previos permanecen preservados.
La verificación final de Opus terminó: 0 P1 y 2 P2 preexistentes de D.
Piloto e instalación verificados; aceptación bloqueada por la puerta vigente.
