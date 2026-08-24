# Diseño de confiabilidad del espacio de acciones de NAO

## Objetivo

Hacer confiables las acciones físicas ya autorizadas del modo inteligente sin ampliar el robot a locomoción ni control articular irrestricto. El incremento implementable cubre LEDs, posturas ligeramente más rápidas y exposición explícita de los behaviors permitidos al modelo.

## Alcance aprobado

- Cambiar la velocidad predeterminada de `set_posture` de `0.30` a `0.35`.
- Mantener `0.50` como límite máximo del registro y de la política.
- Mantener una sola acción corporal por turno y exigir una orden física explícita en la transcripción.
- Corregir `set_led` usando las firmas nativas de NAOqi para LEDs RGB y LEDs de oído.
- Informar a Nemotron los IDs exactos de los behaviors permitidos.
- No añadir marcha, trayectorias, joints libres, behaviors no registrados ni acciones implícitas.

## LEDs

`FaceLeds` y `ChestLeds` usarán la sobrecarga inequívoca `ALLeds.fadeRGB(group, red, green, blue, duration)`, con cinco argumentos y componentes `float` en el rango `0.0..1.0`. Esto evita la selección ambigua observada con el entero RGB empaquetado.

`EarLeds` es un grupo monocromático azul. Usará `ALLeds.fade(group, intensity, duration)`, donde `blue` equivale a intensidad `1.0` y `off` a `0.0`. La política rechazará colores rojo, verde, amarillo o blanco para `EarLeds` en lugar de afirmar que se ejecutaron.

## Posturas

La herramienta seguirá aceptando `Stand`, `StandInit`, `Sit` y `Crouch`. Cuando el modelo omita `speed`, el PC normalizará el argumento a `0.35`; el prompt y sus ejemplos usarán también `0.35`. El ejecutor del NAO continuará limitando cualquier valor solicitado al `max_speed=0.50` del registro.

## Behaviors

`AgentHost.tool_schemas()` incorporará a la herramienta `run_behavior` una lista `allowed_behavior_ids` construida exclusivamente desde `config/behavior_registry.json`. El esquema OpenAI-compatible convertirá esa lista en un `enum`, para que el modelo vea IDs como `wave`, `yes`, `no`, `thinking`, `dance_siu`, `dance_gangnam`, `dance_macarena`, `play_saxophone` y `taichi`.

El prompt explicará que debe emitir `run_behavior` cuando el usuario pida explícitamente saludar, asentir, negar, pensar, bailar, tocar saxofón o hacer taichí. El `ActionExecutor` continuará resolviendo el ID mediante el registro y verificando postura e instalación antes de ejecutar el paquete NAOqi.

## Errores y observabilidad

Los fallos de LEDs y behaviors continuarán apareciendo en el estado web con `status=rejected` y una razón estable. No se ocultarán fallos de facade como acciones completadas. Los logs conservarán nombre, argumentos normalizados, estado y razón, sin incluir secretos.

## Pruebas

- Prueba de la firma NAOqi RGB de cinco argumentos y tipos `float`.
- Prueba de intensidad azul/apagado para `EarLeds`.
- Prueba de rechazo de colores físicamente imposibles en oídos.
- Prueba del valor predeterminado de postura `0.35` y del límite `0.50`.
- Prueba de que el catálogo de behaviors llega como `enum` al cliente del modelo.
- Prueba de que un behavior no registrado sigue rechazado.

## Migración futura sin launcher 6676

La alternativa recomendada es instalar el gateway completo como tarea persistente de Windows y mantenerlo ejecutándose y reconectándose al NAO. En ese diseño el bumper no arranca procesos remotos: solo cambia el modo local, mientras el gateway ya está conectado o intentando reconectar.

El setup del PC instalaría el bundle y guardaría `NAO_GATEWAY_URL`, preferiblemente `ws://nao.local:6674` con una IP explícita como respaldo. La tarea usaría las mismas políticas de batería y reinicio ya corregidas. Después de validar descubrimiento estable del NAO, se retirarían el endpoint `6676`, `RemoteGatewayLauncher` y el servidor de bundle `6677`. Esta migración es una fase separada y no forma parte del incremento inmediato de acciones.

