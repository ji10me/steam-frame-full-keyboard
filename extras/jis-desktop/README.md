# Optional JIS desktop setup for Steam Frame

This opt-in setup adds a full-size JIS keyboard with romaji-to-kana/kanji
conversion through the desktop's existing IBus/Anthy engine. It also provides a
manual **Full Keyboard (show/hide)** launcher that selects the desktop and avoids
overlapping the stock VR keyboard.

The ordinary release, its defaults, and the integrated Japanese modes are
unchanged. This folder contains user profiles and helper scripts, not a new ARM64
binary. Install the normal Full Keyboard release first.

## Scope and requirements

- Steam Frame with the nested KDE desktop, Python 3, IBus/Anthy, `busctl`, `gio`,
  `systemd-run`, and `/opt/steamvr/bin/linuxarm64/vrcmd`.
- Full Keyboard 0.8.2 installed in its standard user directory.
- Standard home-directory configuration paths (`~/.config` and `~/.local`).
- A desktop session already open before showing this keyboard.
- **Replace native keyboard** and **Start with SteamOS** disabled. External JIS
  mode is not supported by the native replacement bridge.

The profiles and helper flow were exercised on SteamOS 0.4.5 with Chrome's X11/XIM
backend. Other applications, floating windows, and future SteamOS versions need
separate validation. This is not input for streamed VR applications.

## What changes

The layout keeps the ordinary JIS geometry and changes only the half/full-width
key action. In the tested desktop keymap, Linux evdev 85 has no symbol, while
evdev 41 resolves to `Zenkaku_Hankaku`. The custom key therefore uses the logical
`Backquote` action, retaining the visible **?/?** label. The language profile
uses the real `jp106`/`jp` keymap and requires this physical action.

The helper starts Anthy separately from KDE's automatic virtual-keyboard UI.
Showing this desktop keyboard disables that UI for the nested session, starts a
user-session IME unit if necessary, and selects Anthy. The stock VR keyboard is
closed through the dashboard lifecycle; Steam files and the global summon
binding are not modified. The original keyboard button still belongs to Steam.

The launcher toggles the installed Full Keyboard process using normal SIGTERM
cleanup. It checks the executable path and process lifetime before stopping it.
Showing it starts a manual transient unit with `--target-language ja-jis-frame`.
No login/startup service is enabled. Service-management commands use the outer
user bus, while the IME receives the nested desktop environment explicitly.

The helpers do not collect typed text, clipboard data, browser fields, or
credentials. Local state and backups stay under the user's home directory.

## Copy this folder to the Frame

On the development computer, copy **only this folder**, rather than keeping a
source checkout on the headset. Replace `FRAME_HOST` with your SSH destination:

```sh
scp -r extras/jis-desktop FRAME_HOST:~/Downloads/
```

On the Frame, open a terminal **inside the KDE desktop**. Quit Full Keyboard
before editing its saved selection so shutdown cannot overwrite the new values.

```sh
cd ~/Downloads/jis-desktop
backup="$HOME/.local/state/framekeyboard-jis-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup"
for relative in .config/framekeyboard .local/bin/framekeyboard-toggle \
  .local/bin/frame-jis-ime-start .local/share/applications/framekeyboard.desktop \
  .config/environment.d/60-framekeyboard-jis.conf; do
  if [ -e "$HOME/$relative" ] || [ -L "$HOME/$relative" ]; then
    mkdir -p "$backup/$(dirname "$relative")"
    cp -a "$HOME/$relative" "$backup/$relative"
  fi
done
printf 'Backup: %s\n' "$backup"

mkdir -p ~/.config/framekeyboard/layouts ~/.config/framekeyboard/languages \
  ~/.local/bin ~/.local/share/applications ~/.config/environment.d
install -m 644 layouts/ja-jis-frame.json ~/.config/framekeyboard/layouts/
install -m 644 languages/ja-jis-frame.json ~/.config/framekeyboard/languages/
install -m 755 bin/framekeyboard-toggle bin/frame-jis-ime-start ~/.local/bin/
```

Select the profiles, retain the other preferences, and create the manual entry:

```sh
python3 - <<'PYSETUP'
import json
import os
from pathlib import Path

home = Path.home()
config = home / '.config/framekeyboard/config.json'
prefs = json.loads(config.read_text(encoding='utf-8')) if config.exists() else {'schema_version': 1}
if prefs.get('replace_native_keyboard') or prefs.get('start_with_steamos'):
    raise SystemExit('Disable native replacement/startup in Settings first.')
prefs.setdefault('active', {}).update(layout='ja-jis-frame-full', language='ja-jis-frame')
prefs['active'].setdefault('theme', 'graphite')

def write(path, text):
    temporary = path.with_name(path.name + '.jis-new')
    temporary.write_text(text, encoding='utf-8')
    os.replace(temporary, path)

write(config, json.dumps(prefs, ensure_ascii=False, indent=2) + '\n')
write(home / '.config/environment.d/60-framekeyboard-jis.conf',
      'FRAMEKEYBOARD_TARGET_LANGUAGE=ja-jis-frame\n')
write(home / '.local/share/applications/framekeyboard.desktop',
      '[Desktop Entry]\nType=Application\nName=Full Keyboard (show/hide)\n'
      'Name[ja]=Full Keyboard\uff08\u8868\u793a\uff0f\u975e\u8868\u793a\uff09\n'
      'Exec=' + str(home / '.local/bin/framekeyboard-toggle') + '\n'
      'Icon=input-keyboard\nTerminal=false\nCategories=Utility;Accessibility;\n')
PYSETUP
update-desktop-database ~/.local/share/applications
```

The environment file is picked up by future desktop sessions. The new launcher
already passes the matching target explicitly, so it works in the current one.
After a release reinstall/update, check whether the generated application entry
has replaced this custom entry; reapply the entry above if needed. User profiles
survive ordinary release updates.

## Desktop IME and Chrome

Run these in the nested desktop terminal to select romaji and start in hiragana:

```sh
gsettings set org.freedesktop.ibus.engine.anthy.common typing-method 0
gsettings set org.freedesktop.ibus.engine.anthy.common input-mode 0
```

An already running Anthy engine can retain its current mode. After selecting the
new launcher, use **?/?** to choose Japanese or ASCII input. The launcher starts
the desktop IME when needed; it is independent of the keyboard's visibility.

For the tested Flatpak Chrome setup, use X11/XIM. Back up an existing flags file
before appending a platform override, and close Chrome before relaunching:

```sh
flatpak override --user --env=GTK_IM_MODULE=xim --env=XMODIFIERS=@im=ibus com.google.Chrome
mkdir -p ~/.var/app/com.google.Chrome/config
printf '%s\n' '--ozone-platform=x11' >> ~/.var/app/com.google.Chrome/config/chrome-flags.conf
```

This applies only to that Chrome installation. The keyboard setup does not edit
browser profiles, cookies, saved passwords, or page content.

## Use and verify

1. Open **Full Keyboard (show/hide)** from the application list. Opening it again
   closes it; the next launch shows it. The dashboard must remain open to type.
2. Select a harmless field in the desktop application.
3. Enter `nihon`, press Space, then Enter. The application should receive **??**.
4. Press **?/?**, then enter `nihon`: it should remain ASCII. Press **?/?** again
   and confirm kana/kanji conversion resumes.

The committed profiles must pass the normal application's `--check`. Rendering
and checking do not inject input. Controller input and IME switching must also be
validated in a disposable field; passing a receiver test does not prove every app.

## Restore the previous setup

Quit Full Keyboard, restore the files from the backup directory, and remove only
addon files that did not exist before installation. Stop the standalone IME unit
using the outer user bus (even from the nested terminal):

```sh
runtime="/run/user/$(id -u)"
XDG_RUNTIME_DIR="$runtime" DBUS_SESSION_BUS_ADDRESS="unix:path=$runtime/bus" \
  systemctl --user stop frame-desktop-jis-ime.service
```

Re-enable KDE's automatic virtual keyboard if it was enabled previously. Run this
from the nested desktop terminal, whose session bus belongs to KWin:

```sh
busctl --address="$DBUS_SESSION_BUS_ADDRESS" set-property org.kde.KWin \
  /VirtualKeyboard org.kde.kwin.VirtualKeyboard enabled b true
```

If Chrome overrides were added only for this setup, restore the prior flags file
and environment overrides as well. Native keyboard replacement was never enabled.
