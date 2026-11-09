# Granola on Linux

[Granola](https://www.granola.ai) only ships for macOS and Windows. It is an Electron app though, so the macOS `.dmg` already holds all of the app's JavaScript, which runs anywhere. It is just attached to a macOS runtime. This repo swaps in the Linux runtime and fixes what breaks. You get a real Linux app. No Wine, no VM, no emulation.

![Granola running on Linux](docs/screenshot.png)

## Run it

1. Download the `.dmg` from [granola.ai/download](https://www.granola.ai/download) (direct link: `https://api.granola.ai/v1/download-latest`)
2. Install what you need: `sudo apt install g++-11 nodejs npm python3 curl make` (Arch: `sudo pacman -S --needed base-devel nodejs npm python 7zip imagemagick`)
3. Run `./granola-linux.sh "Granola - AI Notepad.dmg"`
4. Open Granola from your app menu and sign in

That is it. The script installs to `~/Applications/granola`, adds a desktop entry, registers the `granola://` sign-in handler, and tests the build before it tells you it worked. Run `./uninstall.sh` to undo it.

Set `INSTALL_DIR=` to install somewhere else. You need x86-64 and g++ 11 or newer. Tested on Pop!\_OS (Ubuntu 20.04 base, glibc 2.32) with Granola 7.452.1 and Electron 42.7.0, and on Arch Linux (Hyprland) with Granola 7.749.1 and Electron 45.2.1.

## What works

| | |
|---|---|
| ✅ | Notes, editor, sync, AI features, and search. The core app. |
| ✅ | Sign-in with Google, Microsoft, or SSO |
| ✅ | Encrypted local database that survives restarts |
| ✅ | Microphone recording |
| ⚠️ | System audio capture is limited. The macOS build uses Core Audio to hear the other side of a call. On Linux the app falls back to a browser style capture path. |
| ❌ | Apple Calendar (EventKit). Google and Microsoft calendars still work, since those run on the server. |
| ❌ | Global hotkeys |
| ❌ | Automatic "Granola is transcribing" notice in Google Meet chat. It needs a native helper that only ships for macOS and Windows. |
| ❌ | Auto-update. Run the script again with a newer `.dmg`. |

## Build it yourself

If you would rather not run the script, the conversion takes six steps:

1. Extract the `.dmg` with 7-Zip 21 or newer (`7zz`, or `7z` from a distro `7zip` package). The old `p7zip` cannot read its LZFSE compression.
2. Read the Electron version out of `Electron Framework.framework/.../Info.plist`, then download that exact Linux build.
3. Unzip the Linux runtime into your install folder, delete `resources/default_app.asar`, and rename `electron` to `granola`. With the stock name Electron reports `app.isPackaged = false`, and Granola then looks for its resources in dev paths (no tray icon, for one).
4. Copy `app.asar`, `app.asar.unpacked`, and `icons/` from the bundle into the runtime's `resources/`. Skip every Mac binary, since they all sit behind `darwin` checks.
5. Patch the platform string inside `app.asar` so it reports `Windows`. Granola's API returns a 500 error for `platform=linux`, so sign-in fails without this.
6. Rebuild `better-sqlite3-multiple-ciphers` for Linux with g++ 11 or newer. Granola's fork adds an `updateHook()` and the `tables_used()` virtual table, which no public build has. Older Granola builds bundled that C++ source in `app.asar.unpacked`. Newer ones (7.7xx and later) ship only the macOS binary, so the script builds upstream 12.11.1 with [`patches/patch-bs3.py`](patches/patch-bs3.py). That adds the hook, enables `SQLITE_ENABLE_BYTECODE_VTAB`, and fixes the build for Electron 45's V8.

Four of those six fail with errors that do not point at the real cause. `granola-linux.sh` has the exact commands, with comments explaining each one.

## Notes

- Nothing here gets around licensing or sign-in. You use your own account and the app talks to Granola's real servers. The only patch is a platform label that their API refuses to accept.
- Granola's code belongs to Granola. Do not commit `app.asar` or the `.dmg`. The `.gitignore` covers both.
- Running the script again is safe. It wipes and rebuilds the install folder and leaves your notes in `~/.config/Granola` alone.
- `./uninstall.sh --purge` also removes the local notes cache and login.
- The tray icon is a black macOS template image. If ImageMagick is installed, the script recolors it white so it shows on dark panels (`TRAY_ICON_COLOR=black` for light panels).
- The script checks the Electron zip against Electron's published `SHASUMS256.txt`.
