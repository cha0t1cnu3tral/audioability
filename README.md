# Audioability

Audioability is a Linux screen reader in Python. It listens to AT-SPI, speaks with
Speech Dispatcher, and tries very hard to make your desktop say useful things instead of
silently judging you.

It is early software. Expect sharp edges. The goal is simple: start it, move around, hear
what is focused, interrupt speech with Control, and use screen-reader commands without
needing a ritual sacrifice to the settings menu.

## Fastest Way To Run It

Use the self-contained runner from `dist` on a Linux desktop:

```bash
chmod +x audioability-linux.run
./audioability-linux.run
```

For a smoke test that does not need a desktop accessibility session:

```bash
./audioability-linux.run --dry-run
```

The runner detects apt, dnf/dnf5, yum, pacman, zypper, or apk; installs or updates the
required accessibility and speech packages; verifies its embedded payload; installs
Audioability into `~/.local/share/audioability`; creates `~/.local/bin/audioability`; and
starts the screen reader. Running the same file again updates the dependencies and installed
copy. The previous application payload is retained as `app.previous` for recovery.

To install or update without immediately starting the screen reader:

```bash
./audioability-linux.run --install-only
```

Use `--no-system-packages` when an administrator has already installed the dependencies and
the runner should not invoke the operating system's package manager.

## Run From Source

Use the source installer:

```bash
scripts/install-linux.sh
scripts/run-linux.sh
```

That script installs the Linux system packages `uv sync` cannot fetch, creates
`.venv-linux` with access to distro AT-SPI bindings, then runs `uv sync` into that venv.
This is the boring correct way. The exciting incorrect way is wondering why `pyatspi`
does not exist inside a normal isolated venv.

For a no-desktop sanity check:

```bash
scripts/run-linux.sh --dry-run
```

If the script cannot detect your package manager, install the packages manually. `uv` is
good, but it cannot summon AT-SPI from the void because those bindings are shipped by
distros, not PyPI.

Debian or Ubuntu:

```bash
sudo apt update
sudo apt install -y \
  at-spi2-core \
  espeak-ng \
  gcc \
  libgirepository1.0-dev \
  pkg-config \
  python3-dev \
  python3-gi \
  python3-pyatspi \
  python3-speechd \
  python3-venv \
  speech-dispatcher
```

Fedora:

```bash
sudo dnf install -y \
  at-spi2-core \
  espeak-ng \
  gcc \
  gobject-introspection-devel \
  pkgconf-pkg-config \
  pyatspi \
  python3-devel \
  python3-gobject \
  python3-virtualenv \
  speech-dispatcher
```

Arch:

```bash
sudo pacman -Sy --needed \
  at-spi2-core \
  espeak-ng \
  gcc \
  gobject-introspection \
  pkgconf \
  python \
  python-atspi \
  python-gobject \
  speech-dispatcher
```

Then sync into a venv that can see system site packages:

```bash
python3 -m venv --system-site-packages .venv-linux
UV_PROJECT_ENVIRONMENT=.venv-linux uv sync
scripts/run-linux.sh
```

## Commands

Current key bindings:

```text
Control          stop current speech
Shift            pause/resume speech when supported
sr+Tab           read focused control
sr+T             read window title
sr+B             read current window
sr+End           read status bar
sr+Space         toggle browse/focus mode
sr+R             repeat the last spoken message
sr+S             cycle speech mode
sr+N             hear the command reference
sr+1             input help
sr+F2            pass next key through
sr+Q             quit
```

`sr` means the screen reader key: `CapsLock` or `Insert`. Laptop status bar is
`sr+Shift+End`, because keyboards apparently needed plot twists. The desktop
`KP_Insert`/`KP_0` key is also recognized as `Insert`.

To print the complete command table without starting the screen reader:

```bash
audioability --list-commands
```

Speech modes cycle with `sr+S`:

```text
talk       speak focus changes and explicit commands
on-demand  suppress focus changes, but speak explicit commands
off        suppress normal speech until the mode is changed again
```

Use `sr+Left` and `sr+Right` to select rate, volume, language, voice, punctuation, or
verbosity, then use `sr+Up` and `sr+Down` to change it. Rate, volume, language, voice, and
punctuation are passed to Speech Dispatcher; brief verbosity trims secondary
details from focused-control announcements.

Browse mode supports NVDA-style single-letter navigation. Use the letter to move
forward and add Shift to move backward:

```text
H heading                 L list                 I list item
T table                   K link                 N non-linked text
F form field              U unvisited link       V visited link
E edit field              B button               X check box
C combo box               R radio button         Q block quote
S separator               M frame                G graphic
D landmark                O embedded object      A annotation
P text paragraph          W spelling error       1-9 heading level
```

Comma moves past the current list or table, and Shift+Comma moves to its start.

Editable text uses the application's native caret in focus mode. Left and Right announce
the character crossed by the caret; Control+Left and Control+Right announce the word at
the new caret position. Repeated characters are spoken, and password text remains masked.

NVDA-style table navigation is available after moving to a table in browse mode:

```text
Control+Alt+Left/Right      previous/next column in the current row
Control+Alt+Up/Down         previous/next row in the current column
Control+Alt+Home/End        first/last column in the current row
Control+Alt+PageUp/PageDown first/last row in the current column
```

Cell announcements include the column header and row/column position when available.

Object navigation:

```text
sr+Numpad8      parent object
sr+Numpad4      previous object
sr+Numpad5      current object
sr+Numpad6      next object
sr+Numpad2      first child
sr+Numpad9      previous flat object
sr+Numpad3      next flat object
sr+NumpadMinus  move to focus
sr+NumpadEnter  activate current object
```

## Wayland And X11

Audioability uses AT-SPI, the accessibility bus used by Linux screen readers. That works on
X11 and on Wayland sessions where the compositor and app expose accessibility data.

Keyboard commands use AT-SPI's global device monitor instead of an application-local key
listener. X11 is handled directly. Global Wayland shortcuts require `at-spi2-core` 2.56 or
newer (2.58 or newer is recommended) and a compositor that implements the accessibility
keyboard-monitor protocol. Audioability selects that compositor-backed monitor when it is
available, retains the legacy device monitor for X11 and WSLg, and only falls back to the
registry listener if no device monitor can be opened. Older native Wayland stacks may only
report keys from the focused application. If commands are focus-only, update `at-spi2-core`
and the desktop compositor together.

Audioability keeps a native crash trace at `~/.local/state/audioability/crash.log` (or
`$XDG_STATE_HOME/audioability/crash.log`). If it exits unexpectedly on another computer,
include that file with the bug report. Use `--crash-log PATH` to put it somewhere else.
Detailed accessibility and keyboard events remain opt-in through `--debug-log PATH`.

Translation: if the app publishes useful AT-SPI objects, Audioability can read names, roles,
descriptions, values, visible text, placeholders, states, shortcuts, and child objects. If
the app publishes nothing, Audioability cannot read your mind. Yet.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy
```

The real backend is Linux-only. Tests and `--dry-run` work elsewhere, because developers
also deserve to suffer less.

## Project Layout

- `src/audioability/core/`: app lifecycle, commands, and speech orchestration
- `src/audioability/accessibility/`: AT-SPI backend and accessible object models
- `src/audioability/input/`: key bindings and command routing
- `src/audioability/speech/`: speech controller and drivers
- `scripts/`: Linux install/run helpers
- `tests/`: regression tests, because vibes are not QA

## What `uv sync` Installs

The project now declares the Python-side Linux dependency that PyPI can provide:
`PyGObject>=3.50,<3.52` on Linux.

The `pyatspi` and Speech Dispatcher Python pieces are still distro packages on most Linux
systems. Install the system packages above first, then run `uv sync`. This is annoying, but
it is the honest kind of annoying.
