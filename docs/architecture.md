# Architecture

Audioability is organized around small interfaces so Linux desktop integrations can be
developed without making the whole codebase hard to test.

## Main Components

- Accessibility backend: receives AT-SPI events and exposes normalized accessible objects.
- Speech driver: sends spoken output to Speech Dispatcher or another synthesizer.
- Input layer: maps keyboard gestures to screen-reader commands.
- Core application: coordinates events, commands, focus changes, and speech.

## First Milestones

1. Implement the AT-SPI backend in `audioability.accessibility.backends`.
2. Implement Speech Dispatcher output in `audioability.speech.drivers`.
3. Add a command router for keyboard gestures.
4. Add focused-object speech formatting and regression tests.
