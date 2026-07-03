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

The runner checks for common Linux package managers, installs missing accessibility and
speech packages when it can, unpacks Audioability into `~/.local/share/audioability`, builds
a venv, and starts the screen reader. Yes, it does chores. Somebody had to.

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
CapsLock+Tab     read focused control
CapsLock+T       read window title
CapsLock+B       read current window
CapsLock+End     read status bar
CapsLock+S       cycle speech mode
CapsLock+N       open menu/settings
CapsLock+1       input help
CapsLock+F2      pass next key through
CapsLock+Q       quit
```

`Insert` also works as the screen-reader modifier for those commands. Laptop status bar is
`Insert+Shift+End`, because keyboards apparently needed plot twists.

Object navigation:

```text
CapsLock+Numpad8      parent object
CapsLock+Numpad4      previous object
CapsLock+Numpad5      current object
CapsLock+Numpad6      next object
CapsLock+Numpad2      first child
CapsLock+Numpad9      previous flat object
CapsLock+Numpad3      next flat object
CapsLock+NumpadMinus  move to focus
CapsLock+NumpadEnter  activate current object
```

## Wayland And X11

Audioability uses AT-SPI, the accessibility bus used by Linux screen readers. That works on
X11 and on Wayland sessions where the compositor and app expose accessibility data.

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
