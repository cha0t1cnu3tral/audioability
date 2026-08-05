# Architecture

Audioability is organized around small interfaces so Linux desktop integrations can be
developed without making the whole codebase hard to test.

## Main Components

- Accessibility backend: receives AT-SPI events and exposes normalized accessible objects.
- Speech driver: sends spoken output to Speech Dispatcher or another synthesizer.
- Input layer: maps keyboard gestures to screen-reader commands.
- Core application: coordinates events, commands, focus changes, and speech.

## Runtime Flow

1. The AT-SPI backend subscribes to focus events and uses `Atspi.Device` for global X11
   and Wayland keyboard monitoring. It registers only Audioability command grabs, then
   normalizes live accessible objects into immutable `AccessibleNode` trees. Older AT-SPI
   versions fall back to the legacy keystroke listener.
2. The input layer normalizes Linux key names, tracks held modifiers, and resolves a
   gesture to a command without consuming unassigned application keys.
3. The core application applies browse/focus behavior, object navigation, and speech
   modes before asking the speech controller to announce output.
4. The speech controller suppresses duplicate chatter, interrupts stale output, and
   applies rate, volume, voice, punctuation, and verbosity settings.
5. The Speech Dispatcher driver sends configured output through `spd-say` and falls back
   to visible console messages when speech output cannot be started.

## Reliability Boundaries

- Accessibility trees have bounded depth and child counts so a noisy desktop cannot
  create unbounded reads.
- Object navigation uses node identity, allowing repeated controls with identical names
  and roles to remain distinct.
- Focus and speech duplicate windows independently suppress rapid event storms.
- The real backend is Linux-only; null backends and drivers keep dry runs and tests
  portable.

Every push and pull request runs pytest, Ruff, and strict mypy checks. The nightly release
workflow separately exercises the Linux runner build with native accessibility packages.
