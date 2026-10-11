# t3code-customize

[English](README.md) | [简体中文](README.zh-CN.md)

Your 5 hour and weekly usage, context and tokens per second, right under the T3 Code composer.

Unofficial. Not affiliated with T3 Tools. This fork adds Windows and macOS packaging
to [btsouth/t3code-customize](https://github.com/btsouth/t3code-customize).
It targets an **installed T3 Code Nightly**: Linux AppImage, Windows desktop app,
or macOS `.app` bundle. The stats patches are shared across platforms.

## What you get

- **Usage meters** for your 5 hour and weekly limits, from the limits T3 already gets from your providers.
- **Context** used in the thread. Hover it for the window size, the auto-compaction threshold and a Compact now button.
- **Tokens per second** for the last response, with turn time and token details on hover. Claude rates are measured from the stream; Codex rates are labeled approximate.
- **Cache rate** for the last turn.

The official app's native dependencies and public T3 Connect configuration are
reused. Local signatures and platform restrictions are described below.

## Install

Install T3 Code **Nightly** first. You need Git, Python **3.10+**, an internet
connection and at least approximately **6 GB** of free space. If Node is older
than 24, the tool downloads a private, checksum-verified Node 24 for the host.
The first build takes approximately 5–15 minutes, depending on the machine.

### Windows (PowerShell)

Install Git for Windows and Python, with `git` and `python.exe` on PATH. Clone
this fork, then run Python directly; Git Bash and administrator access are not
required:

```powershell
git clone https://github.com/williamwue/t3code-customize.git
cd t3code-customize
python .\t3code-customize build
```

For a nonstandard installation location, pass the **installed executable**,
not the NSIS installer:

```powershell
python .\t3code-customize build --app 'C:\Apps\T3 Code\T3 Code (Nightly).exe'
```

Alternatively, run the checked-out `install.ps1`; it clones this fork into the
tool's private data directory and builds it. Use `-App` for an explicit executable
and `-Branch` when testing a feature branch. It does not change execution policy.

### macOS

Move the official Nightly `.app` out of the DMG into `/Applications` or
`~/Applications`. Install Git and Python 3.10+, and ensure Apple's `codesign`
and `ditto` tools are available. Then:

```sh
git clone https://github.com/williamwue/t3code-customize.git
cd t3code-customize
python3 ./t3code-customize build
```

For a nonstandard location:

```sh
python3 ./t3code-customize build --app '/path/to/T3 Code (Nightly).app'
```

### Linux

```sh
bash -c "$(curl -fsSL https://raw.githubusercontent.com/williamwue/t3code-customize/main/install.sh)"
```

Or clone this fork and run `python3 ./t3code-customize build`. AppImages in
`~/Applications`, `~/Downloads` and the other standard tool search directories
are discovered automatically. For other paths, pass
`--app /path/to/T3-Code.AppImage`. The old `--appimage` option still works.

### Enable the stats

After the build succeeds, **quit T3 Code fully**. Open **T3 Code (Customized)**
from the Windows Start menu, macOS `~/Applications`, or Linux app launcher.
Enable **Settings > General > Stats for nerds**.

The customized app opens the normal T3 Code main screen; it does not show a
separate setup wizard. Open Settings manually and search for **Stats for nerds**
if you cannot find the switch. It is off by default. Once enabled, the stats
appear below the chat composer; which values are available depends on the
provider and the conversation.

The command wrapper lives in `~/.local/bin` on Linux/macOS, or
`%LOCALAPPDATA%\t3code-customize\bin` on Windows. If it is not on PATH, add that
directory or use `python t3code-customize <command>` from the checkout
(`python3` on Linux/macOS).

## After every T3 Code update

```sh
t3code-customize
```

Update the **official app** first, then run the tool. It pulls the latest patches,
rebuilds for your installed version and tells you when to reopen. Until you run
it, the launcher falls back to stock T3 Code. Windows/macOS customized copies
have automatic updates disabled; update stock from its original launcher.

## When a nightly breaks the patches

Upstream moves fast, and sometimes a nightly changes the code the patches touch. When that happens:

- If you have Claude Code or Codex installed, it offers to port the patches for you right there.
- Otherwise, wait a bit: this repo usually catches up within a day. Then run `t3code-customize` again.
- Or point any coding agent at this repo and ask it to follow [AGENTS.md](AGENTS.md).

Your current T3 Code keeps working the whole time.

## How it works

T3 Code is open source (MIT). This fork keeps the three stats patches and adds
one patch for portable test expectations. The build script:

1. reads your installed application: its exact upstream commit and the public config T3 Connect needs,
2. applies the patches to that commit and runs their tests,
3. rebuilds the web, server and desktop JavaScript,
4. lays it over a copy of your app, checking unchanged archive entries byte for byte,
5. updates Electron's archive integrity metadata and re-signs the macOS copy locally.

Windows builds with a `server.asar` sidecar have both archives patched. Linux
and macOS use the merged `app.asar`. Native libraries and unpacked payloads are
copied from the installed application, without compiling replacement binaries.

Everything runs on your machine. Your official installation and T3 data are
never modified by the build. Running the customized app normally uses the same
T3 profile as stock; quit stock before switching.

## Commands

```
t3code-customize             update the patches and build for your installed T3 Code
t3code-customize status      show what the next launch opens
t3code-customize off | on    switch between stock and the customized build
t3code-customize uninstall   remove it, its launcher, builds and caches
```

## Good to know

- **Bugs:** before reporting anything to T3 Code, run `t3code-customize off`, reopen and check it happens on stock too. Report customization problems here.
- **Windows signatures:** updating embedded archive hashes changes the copied
  executable, so it no longer has the official Authenticode signature. This is
  a local customized copy, not a signed distributable installer.
- **Windows WSL environments:** this version patches the native Windows server.
  The embedded WSL runtime archive stays stock; stats additions on WSL-hosted
  threads are not supported by this adaptation yet.
- **macOS signatures:** the copy is ad-hoc signed, not notarized. Entitlements
  tied to the upstream developer's identity are removed. Keychain groups,
  passkeys and other identity-bound integrations need real-device verification
  and may require signing with your own authorized identity. The build stops
  if signing or signature verification fails.
- **Gatekeeper:** if macOS blocks the locally customized app, use the normal
  **Privacy & Security → Open Anyway** flow for the copy. This tool does not
  disable Gatekeeper or remove quarantine globally.
- **Architectures:** the private Node downloader supports x64 and arm64.
  Build on the same platform and architecture as the installed app; this is
  not a cross-compilation tool.
- **Files on Linux:** data/builds in `~/.local/share/t3code-customize`,
  source/logs in `~/.cache/t3code-customize`.
- **Files on Windows:** data/builds in `%LOCALAPPDATA%\t3code-customize`,
  source/logs in its `cache` subdirectory.
- **Files on macOS:** data/builds in `~/Library/Application Support/t3code-customize`,
  source/logs in `~/Library/Caches/t3code-customize`.

## Development checks

```sh
python -m unittest discover -s tests -v
python t3code-customize verify
```

Use `python3` on Linux/macOS. The first command tests layouts, split/merged
archives, update fallback, locks, command shims and integrity metadata with
fixtures. Windows also exercises the real PE resource API. The second command
applies all patches to their base and runs every test and typecheck in
`checks.json`; it downloads upstream sources and dependencies.

CI runs the platform tests on Linux, Windows and macOS, plus upstream patch
verification on Linux. Fixture tests do not prove a macOS app launches or that
identity-bound integrations work. A real macOS build/start remains an acceptance
gate until tested on a Mac.

## License

MIT, same as T3 Code.
