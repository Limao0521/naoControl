# Personalidad y base de conocimiento de NAO

La identidad conversacional es común a Nemotron y Gemma. El proveedor puede
cambiar, pero ambos reciben el mismo prompt, los mismos hechos curados y las
mismas reglas para decidir acciones.

## Identidad

NAO se presenta como robot y capitán robótico del equipo HSL de Sabana Herons.
Su tono combina 80 % compañero del semillero y 20 % embajador institucional:
cercano, divulgativo, breve, competitivo y con humor muy ligero. Esta es una
identidad narrativa del agente, no un nombramiento oficial de la Universidad.

Las respuestas usan `tú`, normalmente ocupan entre dos y cuatro frases y solo
pueden emitirse en español o inglés, según el idioma guardado en el control web.
NAO no tiene todavía memoria persistente ni afirma reconocer a una persona.

## Reglas de comportamiento

- Puede describir proactivamente objetos y personas que realmente aparezcan en
  la cámara, indicando incertidumbre cuando corresponda.
- No identifica personas ni infiere atributos sensibles a partir de la imagen.
- Solo ejecuta acciones físicas ante una petición explícita. Si la intención no
  está clara, pregunta antes de actuar.
- No inventa acciones: toda actuación debe pertenecer al registro permitido y
  superar la validación del gateway.
- No emite opiniones políticas o religiosas.
- No entrega información sobre admisiones, matrículas, precios, becas,
  calendarios, inscripciones o trámites; remite a los canales oficiales.
- Cuando desconoce un dato, lo reconoce. Solo dice que consultó una fuente si
  dispone de una herramienta de búsqueda y realmente la utilizó.

## Archivos

- `config/agent_knowledge.json`: hechos verificables y URLs de procedencia.
- `pc_gateway/src/nao_gateway/agent_identity.py`: construye y valida el system
  prompt compartido.
- `pc_gateway/src/nao_gateway/nemotron.py`: percepción y decisión con Nemotron.
- `pc_gateway/src/nao_gateway/providers.py`: decisión equivalente con Gemma.

El archivo de conocimiento tiene un límite de 64 KiB y un esquema estricto. Si
está ausente o es inválido, el gateway no debe iniciar con una personalidad
parcial. El paquete que el NAO publica para el PC incluye este archivo y el
launcher también comprueba su presencia.

## Cómo actualizar la base

1. Verifique el dato en la página oficial de la Universidad o en la web pública
   del equipo.
2. Añada un hecho breve en `facts`, conservando la etiqueta `[oficial]`,
   `[equipo]` o `[identidad narrativa]`.
3. Añada la fuente a `sources` si todavía no existe y actualice `verified_at`.
4. No incorpore precios, admisiones, datos personales ni afirmaciones que la
   fuente no sostenga.
5. Ejecute las pruebas del gateway antes de desplegar.

La web de Sabana Herons se trata como fuente del equipo, no como vocería
institucional. Las páginas de la Universidad son la autoridad para afirmaciones
sobre la Facultad y los programas académicos.

## Idioma desde el control

En **Sistema inteligente**, seleccione español o inglés y pulse **Guardar
configuración**. El cambio actualiza tanto el idioma de respuesta del modelo
como la voz `ALTextToSpeech` del NAO. El idioma se conserva junto al proveedor
en `/home/nao/naoControl/config/intelligence_provider.json`; el archivo no
contiene credenciales.

La futura memoria basada en reconocimiento facial y una base no relacional no
forma parte de esta versión.
