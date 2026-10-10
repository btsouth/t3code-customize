# t3code-customize

Your 5 hour and weekly usage, context and tokens per second, right under the T3 Code composer.

Unofficial. Not affiliated with T3 Tools. For T3 Code Nightly on Linux (AppImage) and macOS.

## What you get

- **Usage meters** for your 5 hour and weekly limits, from the limits T3 already gets from your providers.
- **Context** used in the thread. Hover it for the window size, the auto-compaction threshold and a Compact now button.
- **Tokens per second** for the last response, with turn time and token details on hover. Claude rates are measured from the stream; Codex rates are labeled approximate.
- **Cache rate** for the last turn.

Everything else is stock T3 Code, including T3 Connect and the mobile app.

## Install

```sh
bash -c "$(curl -fsSL https://raw.githubusercontent.com/btsouth/t3code-customize/main/install.sh)"
```

Or clone it anywhere and run `./t3code-customize`.

The first run downloads T3 Code's source and build tools, so give it 5 to 15 minutes. Then quit T3 Code fully, open **T3 Code (Customized)** from your app launcher and turn on **Settings > General > Stats for nerds**.

You need git and Python 3. If your Node is older than 24, it fetches its own copy. It uses about 6 GB of disk. If your AppImage isn't in `~/Applications` or `~/Downloads`, run it once with `--appimage /path/to/T3-Code.AppImage`.

On macOS, open **T3 Code (Customized)** from Spotlight, Launchpad or `~/Applications`. See the [macOS guide](docs/macos.md) for setup, day-to-day use and why it loads the patches into your app instead of rebuilding it. It looks for `T3 Code (Nightly).app` in `/Applications` and `~/Applications`; point it elsewhere once with `--app "/path/to/T3 Code (Nightly).app"`.

## After every T3 Code update

```sh
t3code-customize
```

That's it. It pulls the latest patches, rebuilds for your new version and tells you when to reopen. Until you run it, the launcher opens stock T3 Code and tells you why.

## When a nightly breaks the patches

Upstream moves fast, and sometimes a nightly changes the code the patches touch. When that happens:

- If you have Claude Code or Codex installed, it offers to port the patches for you right there.
- Otherwise, wait a bit: this repo usually catches up within a day. Then run `t3code-customize` again.
- Or point any coding agent at this repo and ask it to follow [AGENTS.md](AGENTS.md).

Your current T3 Code keeps working the whole time.

## How it works

T3 Code is open source (MIT). This repo holds three patches and one script. The script:

1. reads your installed AppImage: its exact upstream commit and the public config T3 Connect needs,
2. applies the patches to that commit and runs their tests,
3. rebuilds the web, server and desktop JavaScript,
4. on Linux, lays it over a copy of your app, keeping every native part as shipped, and checks the result byte for byte.

On macOS nothing is copied or re-signed, so your app keeps its signature, keychain access, passkeys and updates. The launcher opens your own `T3 Code (Nightly).app` with a startup hook, loads the rebuilt bundles into it before any app code runs, and closes the hook again. Opening T3 Code any other way gives you stock.

Everything runs on your machine. Your app and your T3 data are never modified.

## Commands

```
t3code-customize             update the patches and build for your installed T3 Code
t3code-customize status      show what the next launch opens
t3code-customize off | on    switch between stock and the customized build
t3code-customize uninstall   remove it, its launcher, builds and caches
```

## Good to know

- **Bugs:** before reporting anything to T3 Code, run `t3code-customize off`, reopen and check it happens on stock too. Report customization problems here.
- **Windows:** not supported yet. The patches are platform independent; only the packaging differs. Your agent can adapt it, and PRs are welcome.
- **macOS:** the customization applies when T3 Code starts from the launcher. If T3 Code is already running, the launcher just brings it forward. It relies on T3 Code allowing a startup hook (`--inspect-brk`); if a release turns that off, the build stops and says so.
- **Files:** builds live in `~/.local/share/t3code-customize`, the source checkout and logs in `~/.cache/t3code-customize`.

## License

MIT, same as T3 Code.
