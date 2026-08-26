# Intelligent Provider Switching Design

## Objective

Allow the NAO web control to select either NVIDIA Nemotron or the PC-local
Gemma service without changing the robot action boundary or copying model
credentials to the NAO.

## Provider boundary

The PC gateway owns model clients. Both providers expose the existing
`perceive(audio_wav, image)` and `decide(transcript, scene, tools)` contract.
Nemotron continues to use the NVIDIA HTTPS endpoint. Gemma uses the loopback
OpenAI-compatible endpoint configured on the PC, defaults to
`http://127.0.0.1:8080/v1`, and never accepts an endpoint supplied by the
browser or robot.

The selected provider name is non-secret configuration. It is persisted
atomically on the NAO and sent through the existing authenticated robot/PC
WebSocket. A PC-side router applies a valid selection before the next turn.
Invalid or unavailable selections do not replace the active provider.

## Web behavior

The intelligent-mode panel shows the selected and active provider, provider
health, and the last provider error. The user can choose `Nemotron NVIDIA` or
`Gemma local`. Saving is rejected while the PC gateway cannot validate the
requested provider. Keys and local service URLs are never rendered or written
to robot storage.

## LED ownership

An intelligence LED controller owns mode colors on `FaceLeds`. A model
requested face color remains visible for three seconds and then restores the
current mode color. Any mode transition cancels the pending restoration before
writing its own color. `ChestLeds` remains persistent. `EarLeds` remains
limited to blue intensity or off.

## Safety and compatibility

The existing action registry, policy engine, explicit-intent checks, signed
protocol, and NAO-local action executor remain the only route to physical
actions. Provider switching does not expose shell execution, arbitrary URLs,
API keys, or direct NAOqi access.
