# Sistema de Conversación con LLM para NAO

Sistema modular que permite al robot NAO mantener conversaciones usando LLMs en la nube.

## Características

- ✅ **Múltiples proveedores de LLM**: Groq, Google Gemini, OpenAI, HuggingFace
- ✅ **STT integrado**: Usa el reconocimiento de voz del robot
- ✅ **TTS integrado**: Usa la síntesis de voz del robot
- ✅ **Historial de conversación**: Mantiene contexto entre mensajes
- ✅ **Modular y extensible**: Fácil de agregar nuevos proveedores
- ✅ **Indicadores LED**: Colores según el estado del sistema

## Obtener API Keys Gratuitas

### 🚀 Groq (RECOMENDADO)

Groq ofrece inferencia muy rápida y un generoso tier gratuito.

1. Ve a [https://console.groq.com/](https://console.groq.com/)
2. Crea una cuenta gratuita con tu email
3. En el menú lateral, ve a **"API Keys"**
4. Clic en **"Create API Key"**
5. Copia tu API key

**Límites gratuitos**: ~14,400 requests/día con modelos Llama 3

### 🌟 Google Gemini

Google ofrece acceso gratuito a Gemini con límites generosos.

1. Ve a [https://aistudio.google.com/](https://aistudio.google.com/)
2. Inicia sesión con tu cuenta de Google
3. En el menú lateral, clic en **"Get API Key"**
4. Clic en **"Create API Key"** o usa una existente
5. Copia tu API key

**Límites gratuitos**: 60 requests/minuto, 1500 requests/día

### 💳 OpenAI

OpenAI da créditos gratuitos a nuevos usuarios.

1. Ve a [https://platform.openai.com/](https://platform.openai.com/)
2. Crea una cuenta
3. Ve a **"API Keys"** en el menú
4. Clic en **"Create new secret key"**
5. Copia tu API key

**Créditos gratuitos**: $5 USD para nuevos usuarios (expiran en 3 meses)

### 🤗 HuggingFace

Usa modelos open source gratuitos.

1. Ve a [https://huggingface.co/](https://huggingface.co/)
2. Crea una cuenta gratuita
3. Ve a **Settings → Access Tokens**
4. Clic en **"New token"**
5. Dale un nombre y permisos de lectura
6. Copia tu token

**Límites gratuitos**: Rate limits básicos, pero sin costo

## Configuración

### 1. Editar archivo de configuración

Edita `llm_conversation/config.py` y reemplaza las API keys:

```python
API_KEYS = {
    'groq': 'tu_api_key_de_groq_aqui',
    'gemini': 'tu_api_key_de_gemini_aqui',
    'openai': 'tu_api_key_de_openai_aqui',
    'huggingface': 'tu_token_de_huggingface_aqui',
}

# Proveedor por defecto
DEFAULT_PROVIDER = 'groq'
```

### 2. Personalizar la personalidad del robot

En el mismo archivo, edita `SYSTEM_PROMPT`:

```python
SYSTEM_PROMPT = """Eres NAO, un robot humanoide amigable y curioso. 
Respondes de manera concisa y clara, con un tono amable y entusiasta.
Tus respuestas deben ser cortas (máximo 2-3 oraciones) para que sean fáciles de escuchar.
Hablas en español."""
```

## Uso

### Modo completo (con STT y TTS)

```bash
# Conectar al robot por SSH
ssh nao@<IP_DEL_ROBOT>

# Navegar al directorio
cd /home/nao/naoControl/scripts/runtime

# Ejecutar con Groq (recomendado)
python nao_conversation.py --nao_ip 127.0.0.1 --provider groq

# Con Google Gemini
python nao_conversation.py --nao_ip 127.0.0.1 --provider gemini

# Con OpenAI
python nao_conversation.py --nao_ip 127.0.0.1 --provider openai

# Pasar API key directamente (sin modificar config.py)
python nao_conversation.py --nao_ip 127.0.0.1 --provider groq --api_key "tu_api_key"
```

### Modo simple (entrada por texto)

Para pruebas sin usar el reconocimiento de voz:

```bash
python nao_conversation.py --nao_ip 127.0.0.1 --provider groq --simple
```

## Indicadores LED

| Color | Significado |
|-------|-------------|
| 🔵 Cyan | Escuchando (esperando que hables) |
| 🟡 Amarillo | Pensando (procesando con LLM) |
| 🟢 Verde | Hablando (respondiendo) |
| ⚫ Apagado | Inactivo |

## Comandos de Voz

Durante la conversación, puedes decir:

- **"Adiós"**, **"Hasta luego"**, **"Chao"** → Termina la conversación
- **"Reiniciar"**, **"Nueva conversación"** → Borra el historial y empieza de nuevo

## Estructura de Archivos

```
nao/scripts/runtime/
├── nao_conversation.py          # Script principal
└── llm_conversation/
    ├── __init__.py
    ├── config.py                # Configuración de API keys y modelos
    └── providers/
        ├── __init__.py
        ├── base_provider.py     # Clase base abstracta
        ├── groq_provider.py     # Proveedor Groq
        ├── gemini_provider.py   # Proveedor Google Gemini
        ├── openai_provider.py   # Proveedor OpenAI
        └── huggingface_provider.py  # Proveedor HuggingFace
```

## Agregar Nuevo Proveedor

Para agregar un nuevo proveedor de LLM:

1. Crea un archivo en `providers/` (ej: `nuevo_provider.py`)
2. Hereda de `BaseLLMProvider`
3. Implementa los métodos requeridos:
   - `default_model`
   - `api_url`
   - `_build_messages()`
   - `_build_request_body()`
   - `_parse_response()`

Ejemplo:

```python
from base_provider import BaseLLMProvider

class NuevoProvider(BaseLLMProvider):
    @property
    def default_model(self):
        return 'modelo-default'
    
    @property
    def api_url(self):
        return 'https://api.nuevo-provider.com/chat'
    
    def _build_messages(self):
        # Construir mensajes en formato del proveedor
        pass
    
    def _build_request_body(self):
        # Construir cuerpo de la petición
        pass
    
    def _parse_response(self, response_data):
        # Extraer texto de la respuesta
        pass
```

## Solución de Problemas

### "Debes configurar tu API key"

Edita `llm_conversation/config.py` y reemplaza `TU_GROQ_API_KEY_AQUI` con tu API key real.

### "HTTP Error 401"

Tu API key es inválida o ha expirado. Genera una nueva.

### "HTTP Error 429"

Has excedido los límites de uso. Espera un momento o cambia a otro proveedor.

### "No te escuché bien"

- Habla más claro y cerca del robot
- Asegúrate de que el ambiente no sea muy ruidoso
- El reconocimiento de voz de NAO funciona mejor con frases cortas

### El robot no habla

- Verifica que el volumen del robot esté alto
- Prueba: `python -c "from naoqi import ALProxy; ALProxy('ALTextToSpeech', '127.0.0.1', 9559).say('Hola')"`

## Comparación de Proveedores

| Proveedor | Velocidad | Calidad | Límites Gratuitos | Recomendado para |
|-----------|-----------|---------|-------------------|------------------|
| **Groq** | ⚡ Muy rápida | ⭐⭐⭐⭐ | Generosos | Uso general |
| **Gemini** | 🚀 Rápida | ⭐⭐⭐⭐⭐ | Buenos | Respuestas complejas |
| **OpenAI** | 🏃 Normal | ⭐⭐⭐⭐⭐ | Limitados | Mejor calidad |
| **HuggingFace** | 🐢 Variable | ⭐⭐⭐ | Sin límite | Experimentación |

## Ejemplo de Sesión

```
$ python nao_conversation.py --nao_ip 127.0.0.1 --provider groq --simple

=== CONVERSACIÓN CON NAO (modo texto) ===
Escribe 'salir' para terminar, 'reiniciar' para nueva conversación

NAO: Hola, soy NAO. ¿De qué quieres hablar?

Tú: Hola NAO, ¿cómo estás?
(pensando...)
NAO: ¡Hola! Estoy muy bien, gracias por preguntar. Me encanta poder 
conversar contigo. ¿Qué te gustaría saber sobre mí?

Tú: ¿Qué puedes hacer?
(pensando...)
NAO: Puedo caminar, bailar, reconocer caras y objetos, y por supuesto, 
¡conversar contigo! También puedo jugar y aprender cosas nuevas.

Tú: salir
NAO: ¡Hasta pronto!
```

## Ver También

- [facial_recording.py](facial_recording.py) - Sistema de grabación con reconocimiento facial
- [video_stream.py](video_stream.py) - Sistema de streaming de video
