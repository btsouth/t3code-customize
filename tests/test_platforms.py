import base64
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

import platform_support as support

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('customize', str(ROOT / 't3code-customize'))
spec = importlib.util.spec_from_loader(loader.name, loader)
customize = importlib.util.module_from_spec(spec)
loader.exec_module(customize)


def archive(path, files):
    tree, data = {'files': {}}, bytearray()
    for name, value in files.items():
        node = tree
        parts = name.split('/')
        for part in parts[:-1]:
            node = node['files'].setdefault(part, {'files': {}})
        node['files'][parts[-1]] = {'offset': str(len(data)), 'size': len(value)}
        data.extend(value)
    header = json.dumps(tree, separators=(',', ':')).encode()
    padded = header + b'\0' * ((-len(header)) % 4)
    pickle = struct.pack('<II', 4 + len(padded), len(header)) + padded
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack('<II', 4, len(pickle)) + pickle + data)


def windows_app(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / 'T3 Code (Nightly).exe').write_bytes(b'MZ-fixture')
    archive(root / 'resources/app.asar', {'package.json': b'{"version":"1-nightly"}'})
    return support.InstalledApp.inspect(root, 'win32')


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        # Resolved, so Windows 8.3 short names (RUNNER~1) match the paths the tool resolves.
        self.root = Path(self.temporary.name).resolve()

    def tearDown(self):
        self.temporary.cleanup()

    def test_storage_paths(self):
        win, cache, config = support.storage_paths(self.root, 'win32', {'LOCALAPPDATA': str(self.root / 'Local')})
        self.assertEqual(win, self.root / 'Local/t3code-customize')
        self.assertEqual(cache, win / 'cache')
        linux, _, _ = support.storage_paths(self.root, 'linux', {'XDG_DATA_HOME': str(self.root / 'data')})
        self.assertEqual(linux, self.root / 'data/t3code-customize')

    def test_unsupported_platform_rejected(self):
        with patch.object(sys, 'platform', 'freebsd14'):
            with self.assertRaisesRegex(support.PlatformError, 'Only Linux, macOS and Windows'):
                support.host_platform()
        for operation in (
            lambda: support.storage_paths(self.root, 'freebsd14', {}),
            lambda: support.InstalledApp.inspect(self.root, 'freebsd14'),
            lambda: support.app_candidates(self.root, 'freebsd14', {}),
            lambda: support.find_app(self.root, {}, system='freebsd14'),
            lambda: support.node_target('freebsd14', 'arm64'),
            lambda: support.node_bin(self.root, 'freebsd14'),
        ):
            with self.subTest(operation=operation):
                with self.assertRaises(support.PlatformError):
                    operation()

    def test_macos_app_bundle(self):
        bundle = self.root / 'Applications/T3 Code (Nightly).app'
        archive(bundle / 'Contents/Resources/app.asar', {'package.json': b'{}'})
        (bundle / 'Contents/MacOS').mkdir(parents=True)
        (bundle / 'Contents/MacOS/T3 Code (Nightly)').write_bytes(b'')
        app = support.InstalledApp.inspect(bundle, 'darwin')
        self.assertEqual(app.resources, bundle / 'Contents/Resources')
        self.assertEqual(app.executable, bundle / 'Contents/MacOS/T3 Code (Nightly)')
        self.assertEqual(support.find_app(self.root, {}, system='darwin', env={}), app)
        self.assertEqual(support.find_app(self.root, {'appimage': str(bundle)}, system='darwin'), app)
        self.assertIn(str(bundle / 'Contents/Resources/app.asar'), [r['path'] for r in app.fingerprint()])
        self.assertEqual(support.node_target('darwin', 'arm64'), ('darwin-arm64', '.tar.xz'))
        self.assertEqual(support.node_bin(self.root, 'darwin'), self.root / 'bin')
        data, _, _ = support.storage_paths(self.root, 'darwin', {})
        self.assertEqual(data, self.root / '.local/share/t3code-customize')
        with self.assertRaises(support.PlatformError):
            app.copy_to(self.root, None, None)
        with self.assertRaises(support.PlatformError):
            support.InstalledApp.inspect(self.root / 'Applications', 'darwin')

    def test_windows_directory_and_executable(self):
        app = windows_app(self.root / 'Installed T3')
        self.assertEqual(support.InstalledApp.inspect(app.executable, 'win32'), app)
        self.assertEqual(app.resources, app.path / 'resources')

    def test_windows_installer_rejected(self):
        installer = self.root / 'T3 Code Setup.exe'
        installer.touch()
        with self.assertRaises(support.PlatformError):
            support.InstalledApp.inspect(installer, 'win32')

    def test_windows_ambiguous_executable_rejected(self):
        app = windows_app(self.root / 'installed')
        (app.path / 'T3 Code.exe').touch()
        with self.assertRaises(support.PlatformError):
            support.InstalledApp.inspect(app.path, 'win32')

    def test_windows_copy_preserves_native_payload(self):
        app = windows_app(self.root / 'installed')
        native = app.resources / 'app.asar.unpacked/native.node'
        native.parent.mkdir()
        native.write_bytes(b'native-unchanged')
        job = self.root / 'job'
        job.mkdir()
        copied = app.copy_to(job, Mock(), None)
        self.assertEqual((copied.resources / 'app.asar.unpacked/native.node').read_bytes(), native.read_bytes())
        self.assertNotEqual(copied.path, app.path)


    def test_windows_autodiscovery(self):
        app = windows_app(self.root / 'Programs/t3code')
        found = support.find_app(self.root, {}, system='win32', env={'LOCALAPPDATA': str(self.root)})
        self.assertEqual(found, app)

    def test_explicit_missing_path_does_not_fall_back(self):
        windows_app(self.root / 'Programs/t3code')
        with self.assertRaises(support.PlatformError):
            support.find_app(self.root, {}, self.root / 'absent', 'win32', {'LOCALAPPDATA': str(self.root)})


    def test_linux_newest_and_replaced_appimage(self):
        folder = self.root / 'Downloads'
        folder.mkdir()
        for version in (2, 10):
            (folder / f'T3-Code-{version}.AppImage').touch()
        app = support.find_app(self.root, {}, system='linux')
        self.assertEqual(app.path.name, 'T3-Code-10.AppImage')
        app = support.find_app(self.root, {'appimage': str(folder / 'T3-Code-1.AppImage')}, system='linux')
        self.assertEqual(app.path.name, 'T3-Code-10.AppImage')

    def test_split_archive_updates_invalidate_fingerprint(self):
        app = windows_app(self.root / 'installed')
        server = app.resources / 'server.asar'
        archive(server, {'before.js': b'a'})
        old = app.fingerprint()
        stat = server.stat()
        archive(server, {'afterx.js': b'a'})
        os.utime(server, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertNotEqual(app.fingerprint(), old)

    def test_node_download_targets(self):
        for system, arch, expected in [('win32', 'x64', ('win-x64', '.zip')),
                                       ('linux', 'x64', ('linux-x64', '.tar.xz'))]:
            self.assertEqual(support.node_target(system, arch), expected)
        self.assertEqual(support.node_bin(self.root, 'win32'), self.root)
        self.assertEqual(support.node_bin(self.root, 'linux'), self.root / 'bin')

    def test_windows_npm_shim_is_shell_free(self):
        script = self.root / 'node_modules/npm/bin/npx-cli.js'
        script.parent.mkdir(parents=True)
        script.touch()
        shim = self.root / 'npx.cmd'
        shim.write_text('SET "NPX_CLI_JS=%~dp0\\node_modules\\npm\\bin\\npx-cli.js"')
        values = {'npx': str(shim), 'node': 'node.exe'}
        with patch.object(support, 'host_platform', return_value='win32'), \
                patch.object(support.shutil, 'which', side_effect=lambda name, **kwargs: values[name]):
            args = support.command_args(['npx', 'argument & %NO_EXECUTION%', 'path with spaces'])
        self.assertEqual(args, ['node.exe', str(script), 'argument & %NO_EXECUTION%', 'path with spaces'])

    def test_windows_pnpm_shim(self):
        script = self.root / 'node_modules/pnpm/bin/pnpm.cjs'
        script.parent.mkdir(parents=True)
        script.touch()
        shim = self.root / 'pnpm.cmd'
        shim.write_text('"%dp0%\\node.exe" "%dp0%\\node_modules\\pnpm\\bin\\pnpm.cjs" %*')
        with patch.object(support, 'host_platform', return_value='win32'), \
                patch.object(support.shutil, 'which', side_effect=lambda name, **kwargs: str(shim) if name == 'pnpm' else 'node.exe'):
            self.assertEqual(support.command_args(['pnpm', 'install']), ['node.exe', str(script), 'install'])

    def test_windows_extensionless_node_shim(self):
        script = self.root / 'vite-plus/bin/vp'
        script.parent.mkdir(parents=True)
        script.write_bytes(b'#!/usr/bin/env node\nconsole.log("fixture")')
        shim = self.root / 'vp.cmd'
        shim.write_text('"%dp0%\\node.exe" "%dp0%\\vite-plus\\bin\\vp" %*')
        with patch.object(support, 'host_platform', return_value='win32'), \
                patch.object(support.shutil, 'which', side_effect=lambda name, **kwargs: str(shim) if name == 'vp' else 'node.exe'):
            self.assertEqual(support.command_args(['vp', 'build']), ['node.exe', str(script), 'build'])

    def test_lock_excludes_another_process_and_releases(self):
        lock = self.root / 'lock'
        code = ('from pathlib import Path; from platform_support import build_lock; '
                'c=build_lock(Path(__import__("sys").argv[1])); c.__enter__()')
        with support.build_lock(lock):
            result = subprocess.run([sys.executable, '-c', code, str(lock)], cwd=ROOT, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'already running', result.stderr)
        with support.build_lock(lock):
            pass


    def test_windows_shortcut_payload_not_shell_interpolated(self):
        calls = []
        repo = self.root / "repo'with;quotes"
        support.write_windows_shortcut(self.root / 'start/app.lnk', repo, Path(sys.executable),
                                       lambda args: calls.append(args))
        code = base64.b64decode(calls[0][-1]).decode('utf-16le')
        self.assertNotIn(str(repo), code)
        self.assertIn('FromBase64String', code)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows resource API')
    def test_real_windows_integrity_resource_round_trip(self):
        executable = self.root / 'fixture.exe'
        shutil.copy2(sys.executable, executable)
        initial = [{'file': 'resources\\app.asar', 'alg': 'SHA256', 'value': 'first'}]
        support.windows_integrity(executable, initial)
        self.assertEqual(support.windows_integrity(executable), initial)
        initial[0]['value'] = 'second'
        support.windows_integrity(executable, initial)
        self.assertEqual(support.windows_integrity(executable), initial)


class OverlayTests(unittest.TestCase):
    setUp = PlatformTests.setUp
    tearDown = PlatformTests.tearDown

    def test_merged_archive_replaces_bundles_and_removes_old_chunks(self):
        app = windows_app(self.root / 'installed')
        archive(app.resources / 'app.asar', {'package.json': b'{}', 'native.node': b'native',
                'apps/desktop/dist-electron/main.cjs': b'old',
                'apps/server/dist/bin.mjs': b'old',
                'apps/server/dist/client/index.html': b'old',
                'apps/server/dist/old-chunk.mjs': b'stale chunk'})
        source = self.root / 'source'
        for name, value in {'apps/desktop/dist-electron/main.cjs': b'statsForNerds',
                            'apps/server/dist/bin.mjs': b'claude_observed',
                            'apps/server/dist/client/index.html': b'new',
                            'apps/server/dist/client/stats.js': b'statsForNerds'}.items():
            file = source / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(value)
        with patch.object(customize, 'SOURCE', source):
            customize.overlay_app(app, self.root, {})
        result = customize.Archive(app.resources / 'app.asar')
        try:
            self.assertEqual(result.read('native.node'), b'native')
            self.assertEqual(result.read('apps/server/dist/client/index.html'), b'new')
            self.assertNotIn('apps/server/dist/old-chunk.mjs', result.entries)
        finally:
            result.close()
    def test_split_archives_preserve_unmodified_payload(self):
        app = windows_app(self.root / 'installed')
        archive(app.resources / 'app.asar', {'package.json': b'{}', 'native.node': b'original native',
                'apps/desktop/dist-electron/main.cjs': b'old desktop'})
        archive(app.resources / 'server.asar', {'native.node': b'original server native',
                'apps/server/dist/bin.mjs': b'old server',
                'apps/server/dist/client/index.html': b'old web'})
        source = self.root / 'source'
        files = {'apps/desktop/dist-electron/main.cjs': b'statsForNerds',
                 'apps/server/dist/bin.mjs': b'claude_observed',
                 'apps/server/dist/client/index.html': b'web',
                 'apps/server/dist/client/new.js': b'statsForNerds'}
        for name, value in files.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        with patch.object(customize, 'SOURCE', source):
            customize.overlay_app(app, self.root, {})
        for filename, value in [('app.asar', b'original native'), ('server.asar', b'original server native')]:
            result = customize.Archive(app.resources / filename)
            try:
                self.assertEqual(result.read('native.node'), value)
            finally:
                result.close()
        desktop = customize.Archive(app.resources / 'app.asar')
        try:
            self.assertEqual(desktop.read('apps/desktop/dist-electron/main.cjs'), b'statsForNerds')
            self.assertNotIn('apps/server/dist/bin.mjs', desktop.entries)
        finally:
            desktop.close()

    def test_missing_stats_marker_rejects_overlay(self):
        stock = self.root / 'app.asar'
        archive(stock, {'apps/desktop/dist-electron/main.cjs': b'original'})
        source = self.root / 'source'
        output = source / 'apps/desktop/dist-electron/main.cjs'
        output.parent.mkdir(parents=True)
        output.write_bytes(b'missing stats')
        with self.assertRaises(customize.Stop):
            customize.overlay(stock, self.root / 'new.asar', source, {}, ('apps/desktop/dist-electron',))

    def test_public_config_must_survive_overlay(self):
        stock = self.root / 'app.asar'
        archive(stock, {'apps/desktop/dist-electron/main.cjs': b'statsForNerds public-config-fixture'})
        source = self.root / 'source'
        output = source / 'apps/desktop/dist-electron/main.cjs'
        output.parent.mkdir(parents=True)
        output.write_bytes(b'statsForNerds')
        with self.assertRaises(customize.Stop):
            customize.overlay(stock, self.root / 'new.asar', source, {'PUBLIC': 'public-config-fixture'},
                              ('apps/desktop/dist-electron',))

    def test_disabled_and_stale_launch_fall_back_to_stock(self):
        app = windows_app(self.root / 'installed')
        copied = windows_app(self.root / 'copied')
        state = {'build': str(copied.path), 'stock': app.fingerprint()}
        disabled = self.root / 'disabled'
        with patch.object(customize, 'SYSTEM', 'win32'), patch.object(customize, 'MAC', False), patch.object(customize, 'installed_app', return_value=app), \
                patch.object(customize, 'load', return_value=state), patch.object(customize, 'DISABLED', disabled):
            self.assertEqual(customize.launch_target(), (copied.executable, None))
            disabled.touch()
            self.assertEqual(customize.launch_target(), (app.executable, None))
            disabled.unlink()
            (app.executable).write_bytes(b'updated exe')
            target, notice = customize.launch_target()
            self.assertEqual(target, app.executable)
            self.assertIn('updated', notice)

    def test_macos_launch_uses_the_build_folder_until_the_app_changes(self):
        bundle = self.root / 'T3 Code (Nightly).app'
        archive(bundle / 'Contents/Resources/app.asar', {'package.json': b'{}'})
        (bundle / 'Contents/MacOS').mkdir(parents=True)
        (bundle / 'Contents/MacOS/T3 Code (Nightly)').write_bytes(b'')
        app = support.InstalledApp.inspect(bundle, 'darwin')
        build = self.root / 'builds/one/build'
        build.mkdir(parents=True)
        (build / 'inject.cjs').write_text('')
        state = {'build': str(build), 'stock': app.fingerprint()}
        disabled = self.root / 'disabled'
        with patch.object(customize, 'SYSTEM', 'darwin'), patch.object(customize, 'MAC', True), \
                patch.object(customize, 'installed_app', return_value=app), \
                patch.object(customize, 'load', return_value=state), patch.object(customize, 'DISABLED', disabled):
            self.assertEqual(customize.launch_target(), (build.resolve(), None))
            disabled.touch()
            self.assertEqual(customize.launch_target(), (bundle, None))
            disabled.unlink()
            archive(bundle / 'Contents/Resources/app.asar', {'package.json': b'{"updated":1}'})
            target, notice = customize.launch_target()
            self.assertEqual(target, bundle)
            self.assertIn('updated', notice)

    def test_macos_launcher_app(self):
        bundle = self.root / 'T3 Code (Nightly).app'
        archive(bundle / 'Contents/Resources/app.asar', {'package.json': b'{}'})
        (bundle / 'Contents/Resources/icon.icns').write_bytes(b'icon')
        (bundle / 'Contents/MacOS').mkdir(parents=True)
        app = support.InstalledApp.inspect(bundle, 'darwin')
        launcher = self.root / 'Applications/T3 Code (Customized).app'
        with patch.object(customize, 'MAC_LAUNCHER', launcher), patch.object(customize, 'CACHE', self.root / 'cache'):
            customize.install_mac_launcher(app)
        import plistlib
        info = plistlib.loads((launcher / 'Contents/Info.plist').read_bytes())
        self.assertEqual(info['CFBundleExecutable'], 'launch')
        self.assertTrue(info['LSUIElement'])
        script = (launcher / 'Contents/MacOS/launch').read_text()
        self.assertIn(' launch >>', script)
        self.assertEqual((launcher / 'Contents/Resources/icon.icns').read_bytes(), b'icon')

    def test_uninstall_removes_owned_paths_with_lock_outside(self):
        data, cache, config = self.root / 'data', self.root / 'data/cache', self.root / 'data/config'
        cache.mkdir(parents=True)
        config.mkdir()
        (cache / 'fixture').touch()
        bin_path, launcher = self.root / 'bin.cmd', self.root / 'launcher.lnk'
        bin_path.touch()
        launcher.touch()
        with patch.object(customize, 'DATA', data), patch.object(customize, 'CACHE', cache), \
                patch.object(customize, 'CONFIG', config), patch.object(customize, 'BIN', bin_path), \
                patch.object(customize, 'DESKTOP', launcher), patch.object(customize, 'SYSTEM', 'win32'), patch.object(customize, 'MAC', False), \
                patch.object(customize, 'say'), support.build_lock(self.root / 'outside.lock'):
            customize.cmd_uninstall(None)
        self.assertFalse(data.exists())
        self.assertFalse(bin_path.exists())
        self.assertFalse(launcher.exists())

    def test_windows_launcher_removes_inherited_node_mode(self):
        app = windows_app(self.root / 'installed')
        copied = windows_app(self.root / 'copied')
        environment = {'ELECTRON_RUN_AS_NODE': '1', 'ELECTRON_NO_ASAR': '1', 'NODE_OPTIONS': '--inspect'}
        from types import SimpleNamespace
        with patch.object(customize, 'SYSTEM', 'win32'), patch.object(customize, 'MAC', False), patch.object(customize, 'installed_app', return_value=app), \
                patch.object(customize, 'launch_target', return_value=(copied.executable, None)), \
                patch.dict(os.environ, environment), patch.object(customize.subprocess, 'Popen') as spawn:
            customize.cmd_launch(SimpleNamespace(rest=['--', 'argument with spaces']))
        args, kwargs = spawn.call_args
        self.assertEqual(args[0], [str(copied.executable), 'argument with spaces'])
        self.assertEqual(kwargs['env']['T3CODE_DISABLE_AUTO_UPDATE'], 'true')
        self.assertNotIn('ELECTRON_RUN_AS_NODE', kwargs['env'])
        self.assertNotIn('NODE_OPTIONS', kwargs['env'])


if __name__ == '__main__':
    unittest.main()
