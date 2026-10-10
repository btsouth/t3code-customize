# T3 Code (Customized) on macOS

The patches and the build are the same as on Linux. Only the last step differs: on macOS
nothing is copied, repacked or re-signed. A launcher opens your own `T3 Code (Nightly).app`
and loads the rebuilt bundles into it as it starts.

## Install

You need git, Python 3 and T3 Code Nightly in `/Applications` or `~/Applications`.

```sh
bash -c "$(curl -fsSL https://raw.githubusercontent.com/btsouth/t3code-customize/main/install.sh)"
```

1. The first run downloads T3 Code's source and build tools, so give it 5 to 15 minutes.
   It uses about 6 GB of disk.
2. Quit T3 Code fully (Cmd+Q, not just closing the window).
3. Open **T3 Code (Customized)** from Spotlight, Launchpad or `~/Applications`.
4. Turn on **Settings > General > Stats for nerds**.

If your app is somewhere else, point to it once:

```sh
t3code-customize --app "/path/to/T3 Code (Nightly).app"
```

`t3code-customize` lives in `~/.local/bin`. If that is not on your `PATH`, add it, or run
`~/.local/bin/t3code-customize`.

## Day to day

- Always open T3 Code with **T3 Code (Customized)**. Opening T3 Code from the Dock, Finder
  or a `t3code://` link starts it stock. You can pin the running app to the Dock as usual;
  just start it with the launcher.
- If T3 Code is already running, the launcher only brings it forward. Quit it fully and
  open the launcher again to get the customization.
- T3 Code updates itself as usual. After an update, run `t3code-customize` again. Until
  you do, the launcher opens stock T3 Code and tells you why.

`t3code-customize status`, `off`, `on` and `uninstall` work as on Linux. `uninstall` also
removes the launcher from `~/Applications`.

## Why it injects instead of rebuilding the app

On Linux, the tool rebuilds the JavaScript, packs it into a copy of the AppImage's
`app.asar` and runs that copy. Doing the same on macOS would break more than it fixes:

- **The signature.** Every file in a macOS app is covered by T3's Developer ID signature.
  Changing `app.asar` (and the asar hash in `Info.plist`) invalidates it, so the copy would
  have to be re-signed by you, ad hoc.
- **The entitlements.** T3's signature carries entitlements only T3's team can use:
  associated domains for passkeys, plus its team and application identifiers. macOS refuses
  to launch an ad-hoc signed app that claims them, so they would have to be removed. That
  breaks passkey sign-in to T3 Connect.
- **The keychain.** T3 keeps its stored secrets in a keychain item tied to its signature.
  An ad-hoc copy gets a new identity on every rebuild, so macOS would ask for keychain
  access again after each one.
- **Updates and links.** The updater checks that an update is signed by the same identity
  as the running app, so it fails in a re-signed copy. Two apps with the same bundle ID
  also compete for `t3code://` links, so sign-in callbacks can land in the wrong one.
- **Size.** Every build would carry a full copy of the app.

Injecting avoids all of that. Your app stays byte for byte as T3 shipped it, signature
and entitlements included. Keychain, passkeys, updates and links behave exactly as in
stock. The tool only adds a folder of rebuilt JavaScript and the launcher.

## How the injection works

The rebuilt bundles go in `~/.local/share/t3code-customize/current/overlay`. When you open
the launcher, it:

1. starts your app with `--inspect-brk` on a random local port, so it waits before running
   any of its own code,
2. connects with `connect.mjs`, which runs on T3 Code's own runtime, and loads
   `inject.cjs` into it,
3. lets the app continue. The debug port closes as soon as the app's code starts.

`inject.cjs` uses Node's module hooks. When the app loads a file from
`apps/desktop/dist-electron` or `apps/server/dist` inside `app.asar` and the overlay has a
rebuilt copy, it gets the rebuilt copy under the original path. `__dirname`, `electron`
and the app's native modules therefore resolve exactly as in stock. Reads of the web
client in `apps/server/dist/client` are redirected to the overlay. The backend and its
workers get `inject.cjs` through `--require`, so they load the rebuilt server as well.

This relies on two things T3 Code's macOS builds allow today: the `--inspect-brk` startup
switch (Electron's `EnableNodeCliInspectArguments` fuse) and an unchanged `boot.cjs`
entry point. The build checks both and stops with a clear message if a release changes
them. Your T3 Code is never modified, so it keeps working either way.

## Troubleshooting

- **The stats bar is missing.** Make sure T3 Code was fully quit before you opened the
  launcher, then check that the launcher log ends with `Opened T3 Code with the
  customization`.
- **A notification says "Opened stock T3 Code".** It names the reason. Usually T3 Code was
  updated and you need to run `t3code-customize` again.
- **Logs.** Launcher: `~/.cache/t3code-customize/logs/launch.log`. Builds: the other files
  in the same folder.
- **Running it from a terminal inside T3 Code** works. The tool clears the
  `ELECTRON_RUN_AS_NODE` variable that T3 sets for its terminals.
- **Before reporting a bug to T3 Code**, run `t3code-customize off`, quit T3 Code, reopen
  it and check the problem happens on stock too.
