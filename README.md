# t3code-customize

Your 5 hour and weekly usage, context and tokens per second, right under the T3 Code composer.

Unofficial. Not affiliated with T3 Tools. For T3 Code Nightly on Linux (AppImage).

## What you get

- **Usage meters** for your 5 hour and weekly limits, from the limits T3 already gets from your providers.
- **Context** used in the thread. Hover it for the window size, the auto-compaction threshold and a Compact now button.
- **Tokens per second** for the last response, with turn time and token details on hover. Claude rates are measured from the stream; Codex rates are labeled approximate.
- **Cache rate** for the last turn.
- **Subscription switch** when you have more than one signed-in subscription that offers your model. If the current one is on pace to run out before its 5 hour or weekly window resets, a chip like **Opus 5.5 on Personal →** switches the thread to the same model on the one with the most room. It also points out a subscription whose weekly allowance resets within a day mostly unused. Hover it for the reasoning.

Everything else is stock T3 Code, including T3 Connect and the mobile app.

## Install

```sh
bash -c "$(curl -fsSL https://raw.githubusercontent.com/btsouth/t3code-customize/main/install.sh)"
```

Or clone it anywhere and run `./t3code-customize`.

The first run downloads T3 Code's source and build tools, so give it 5 to 15 minutes. Then quit T3 Code fully, open **T3 Code (Customized)** from your app launcher and turn on **Settings > General > Stats for nerds**.

You need git and Python 3. If your Node is older than 24, it fetches its own copy. It uses about 6 GB of disk. If your AppImage isn't in `~/Applications` or `~/Downloads`, run it once with `--appimage /path/to/T3-Code.AppImage`.

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

T3 Code is open source (MIT). This repo holds four patches and one script. The script:

1. reads your installed AppImage: its exact upstream commit and the public config T3 Connect needs,
2. applies the patches to that commit and runs their tests,
3. rebuilds the web, server and desktop JavaScript,
4. lays it over a copy of your app, keeping every native part as shipped, and checks the result byte for byte.

Everything runs on your machine. Your AppImage and your T3 data are never modified.

## Commands

```
t3code-customize             update the patches and build for your installed T3 Code
t3code-customize status      show what the next launch opens
t3code-customize off | on    switch between stock and the customized build
t3code-customize uninstall   remove it, its launcher, builds and caches
```

## Good to know

- **Bugs:** before reporting anything to T3 Code, run `t3code-customize off`, reopen and check it happens on stock too. Report customization problems here.
- **macOS and Windows:** not supported yet. The patches are platform independent; only the packaging differs. Your agent can adapt it, and PRs are welcome.
- **Files:** builds live in `~/.local/share/t3code-customize`, the source checkout and logs in `~/.cache/t3code-customize`.

## License

MIT, same as T3 Code.
