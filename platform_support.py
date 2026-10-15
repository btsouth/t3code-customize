"""Installed Electron layouts and host operations for the customization tool."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import struct
import subprocess
import sys


class PlatformError(Exception):
    pass


def host_platform(system=None):
    system = system or sys.platform
    if system not in ('win32', 'linux', 'darwin'):
        raise PlatformError(f'Unsupported platform: {system}. Only Linux, macOS and Windows are supported.')
    return system


def host_arch():
    machine = platform.machine().lower()
    names = {'amd64': 'x64', 'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}
    if machine not in names:
        raise PlatformError(f'Unsupported architecture: {machine}')
    return names[machine]


def storage_paths(home, system=None, env=None):
    system = host_platform(system)
    env = os.environ if env is None else env
    if system == 'win32':
        root = Path(env.get('LOCALAPPDATA') or home / 'AppData/Local') / 't3code-customize'
        return root, root / 'cache', root / 'config'
    return (Path(env.get('XDG_DATA_HOME') or home / '.local/share') / 't3code-customize',
            Path(env.get('XDG_CACHE_HOME') or home / '.cache') / 't3code-customize',
            Path(env.get('XDG_CONFIG_HOME') or home / '.config') / 't3code-customize')


def asar_header_hash(path):
    with Path(path).open('rb') as source:
        _, _, _, length = struct.unpack('<4I', source.read(16))
        header = source.read(length)
        if len(header) != length:
            raise PlatformError(f'Truncated ASAR header: {path}')
    return hashlib.sha256(header).hexdigest()


@dataclass(frozen=True)
class InstalledApp:
    path: Path
    system: str
    resources: Path
    executable: Path

    @classmethod
    def inspect(cls, value, system=None):
        system = host_platform(system)
        path = Path(value).expanduser().resolve()
        if system == 'linux':
            if not path.is_file() or path.suffix != '.AppImage':
                raise PlatformError(f'Expected an installed T3 Code AppImage: {path}')
            return cls(path, system, path.parent, path)
        if system == 'darwin':
            resources = path / 'Contents/Resources'
            if path.suffix != '.app' or not (resources / 'app.asar').is_file():
                raise PlatformError(f'Expected an installed T3 Code app bundle: {path}')
            return cls(path, system, resources, path / 'Contents/MacOS' / path.stem)
        explicit_exe = path if path.suffix.lower() == '.exe' else None
        path = path.parent if explicit_exe else path
        resources = path / 'resources'
        candidates = sorted(path.glob('T3 Code*.exe'))
        candidates = [p for p in candidates if 'uninstall' not in p.name.lower()]
        if not explicit_exe and len(candidates) != 1:
            raise PlatformError(f'Pass the installed T3 Code executable with --app: {path}')
        executable = explicit_exe or candidates[0]
        if not executable.is_file() or not (resources / 'app.asar').is_file():
            raise PlatformError(f'This is not an installed T3 Code application: {path}')
        return cls(path, system, resources, executable)

    def fingerprint(self):
        paths = [self.path] if self.system == 'linux' else [self.executable, *self.resources.glob('*.asar')]
        records = []
        for path in sorted(paths):
            stat = path.stat()
            item = {'path': str(path), 'size': stat.st_size, 'mtime': stat.st_mtime_ns}
            if path.suffix == '.asar':
                item['header'] = asar_header_hash(path)
            records.append(item)
        return records

    def copy_to(self, job, run, log):
        if self.system == 'darwin':
            raise PlatformError('The macOS app is read in place and never copied.')
        if self.system == 'linux':
            run([str(self.path), '--appimage-extract'], cwd=job, log=log)
            root = job / 'squashfs-root'
            return InstalledApp(root, self.system, root / 'resources', root / 'AppRun')
        root = job / 'application'
        shutil.copytree(self.path, root, symlinks=True)
        return InstalledApp.inspect(root, self.system)


def app_candidates(home, system=None, env=None):
    system = host_platform(system)
    env = os.environ if env is None else env
    if system == 'win32':
        local = Path(env.get('LOCALAPPDATA') or home / 'AppData/Local')
        roots = [local / 'Programs']
        roots += [Path(env[key]) for key in ('ProgramFiles', 'ProgramFiles(x86)') if env.get(key)]
        return [base / folder for base in roots
                for folder in ('t3code', 't3code-nightly', 'T3 Code (Nightly)', 'T3 Code')]
    if system == 'darwin':
        return [folder / 'T3 Code (Nightly).app' for folder in (Path('/Applications'), home / 'Applications')]
    folders = ['Applications', 'Downloads', 'AppImages', 'Apps', '.local/bin', 'bin', 'opt']
    found = [p for folder in folders for p in (home / folder).glob('T3-Code*.AppImage') if p.is_file()]
    def version_key(path):
        return [int(p) if p.isdigit() else p for p in re.split(r'(\d+)', path.name)]
    return sorted(found, key=version_key, reverse=True)


def find_app(home, config, explicit=None, system=None, env=None):
    system = host_platform(system)
    if explicit:
        return InstalledApp.inspect(explicit, system)
    saved = config.get('app') or config.get('appimage')
    if saved:
        path = Path(saved)
        if path.exists():
            return InstalledApp.inspect(path, system)
        if system == 'linux':
            def key(p):
                return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', p.name)]
            matches = sorted(path.parent.glob('T3-Code*.AppImage'), key=key, reverse=True)
            if matches:
                return InstalledApp.inspect(matches[0], system)
    for path in app_candidates(home, system, env):
        if path.exists():
            try:
                return InstalledApp.inspect(path, system)
            except PlatformError:
                continue
    raise PlatformError('Could not find installed T3 Code Nightly. Pass --app with the AppImage, '
                        'the macOS T3 Code (Nightly).app or the installed Windows executable (not the installer).')


def node_target(system=None, arch=None):
    system, arch = host_platform(system), arch or host_arch()
    target = {'win32': 'win', 'linux': 'linux', 'darwin': 'darwin'}[system]
    return f'{target}-{arch}', ('.zip' if system == 'win32' else '.tar.xz')


def node_bin(folder, system=None):
    return folder if host_platform(system) == 'win32' else folder / 'bin'


def command_args(args, env=None):
    """Run npm/pnpm Node shims without a command shell on Windows."""
    args = list(map(str, args))
    if host_platform() != 'win32':
        return args
    env = os.environ if env is None else env
    executable = shutil.which(args[0], path=env.get('PATH'))
    if not executable or Path(executable).suffix.lower() not in ('.cmd', '.bat'):
        return args
    shim = Path(executable)
    text = shim.read_text(encoding='utf-8')
    # pnpm and npm generate both forms. Resolve the JS entry, never interpolate
    # arguments into cmd.exe (paths and CLI arguments may contain shell syntax).
    entries = re.findall(r'%[~]?dp0%?[\\/]([^"\r\n]+)', text, re.I)
    for entry in reversed(entries):
        script = (shim.parent / entry.replace('\\', '/')).resolve()
        if script.is_file():
            with script.open('rb') as source:
                header = source.read(80)
            if script.suffix.lower() not in ('.js', '.mjs', '.cjs') and not header.startswith(b'#!/usr/bin/env node'):
                continue
            node = shutil.which('node', path=env.get('PATH'))
            if not node:
                raise PlatformError('Node is required to run ' + args[0])
            return [node, str(script), *args[1:]]
    raise PlatformError(f'Cannot resolve the Node entry in {shim}. Install a standard npm/pnpm shim.')


@contextmanager
def build_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never truncate: Windows locks one existing byte and another process must
    # not rewrite it while this process owns the lock.
    with path.open('a+b') as lock:
        if host_platform() == 'win32':
            import msvcrt
            lock.seek(0, 2)
            if lock.tell() == 0:
                lock.write(b'\0')
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise PlatformError('Another t3code-customize is already running.')
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise PlatformError('Another t3code-customize is already running.')
            yield


def windows_integrity(executable, values=None):
    """Read or replace Electron's embedded ASAR header hashes in a copied EXE."""
    import ctypes
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'LoadLibraryExW': ([w.LPCWSTR, w.HANDLE, w.DWORD], w.HANDLE),
        'FindResourceW': ([w.HANDLE, w.LPCWSTR, w.LPCWSTR], w.HANDLE),
        'SizeofResource': ([w.HANDLE, w.HANDLE], w.DWORD),
        'LoadResource': ([w.HANDLE, w.HANDLE], w.HANDLE),
        'LockResource': ([w.HANDLE], ctypes.c_void_p),
        'FreeLibrary': ([w.HANDLE], w.BOOL),
        'BeginUpdateResourceW': ([w.LPCWSTR, w.BOOL], w.HANDLE),
        'UpdateResourceW': ([w.HANDLE, w.LPCWSTR, w.LPCWSTR, w.WORD, ctypes.c_void_p, w.DWORD], w.BOOL),
        'EndUpdateResourceW': ([w.HANDLE, w.BOOL], w.BOOL),
    }
    for name, (args, result) in signatures.items():
        getattr(kernel, name).argtypes, getattr(kernel, name).restype = args, result
    def require(value):
        if not value:
            raise ctypes.WinError(ctypes.get_last_error())
        return value
    if values is None:
        handle = require(kernel.LoadLibraryExW(str(executable), None, 2))
        try:
            resource = kernel.FindResourceW(handle, 'ElectronAsar', 'Integrity')
            if not resource:
                if ctypes.get_last_error() in (1812, 1813, 1814):
                    return None
                require(resource)
            data = require(kernel.LockResource(require(kernel.LoadResource(handle, resource))))
            return json.loads(ctypes.string_at(data, kernel.SizeofResource(handle, resource)))
        finally:
            kernel.FreeLibrary(handle)
    callback_type = ctypes.WINFUNCTYPE(w.BOOL, w.HANDLE, w.LPCWSTR, w.LPCWSTR, w.WORD, ctypes.c_ssize_t)
    kernel.EnumResourceLanguagesW.argtypes = [w.HANDLE, w.LPCWSTR, w.LPCWSTR, callback_type, ctypes.c_ssize_t]
    kernel.EnumResourceLanguagesW.restype = w.BOOL
    languages = []
    callback = callback_type(lambda module, kind, name, language, value: languages.append(language) or True)
    library = require(kernel.LoadLibraryExW(str(executable), None, 2))
    try:
        found = kernel.EnumResourceLanguagesW(library, 'Integrity', 'ElectronAsar', callback, 0)
        if not found and ctypes.get_last_error() not in (1812, 1813, 1814):
            require(found)
    finally:
        kernel.FreeLibrary(library)
    handle = require(kernel.BeginUpdateResourceW(str(executable), False))
    payload = json.dumps(values, separators=(',', ':')).encode('utf-8')
    buffer = ctypes.create_string_buffer(payload)
    try:
        for language in languages or [1033]:
            require(kernel.UpdateResourceW(handle, 'Integrity', 'ElectronAsar', language, buffer, len(payload)))
    except BaseException:
        kernel.EndUpdateResourceW(handle, True)
        raise
    require(kernel.EndUpdateResourceW(handle, False))
    if windows_integrity(executable) != values:
        raise PlatformError('Windows ASAR integrity resource verification failed.')


def finalize_copy(app, run, log):
    if app.system == 'win32':
        # Customized copies are rebuilt after the official installation updates.
        (app.resources / 'app-update.yml').unlink(missing_ok=True)
    hashes = {p.name: asar_header_hash(p) for p in app.resources.glob('*.asar')}
    if app.system == 'win32':
        entries = windows_integrity(app.executable)
        if entries is not None:
            for entry in entries:
                name = entry['file'].replace('\\', '/').split('/')[-1]
                if name not in hashes:
                    raise PlatformError(f'Missing archive referenced by Electron integrity: {name}')
                entry['value'] = hashes[name]
            windows_integrity(app.executable, entries)


def write_cli(bin_path, repo, python):
    bin_path.parent.mkdir(parents=True, exist_ok=True)
    if host_platform() == 'win32':
        def batch_literal(value):
            return str(value).replace('%', '%%')
        bin_path.write_text('@echo off\nsetlocal DisableDelayedExpansion\n"' + batch_literal(python) + '" "' +
                            batch_literal(repo / 't3code-customize') + '" %*\n', encoding='utf-8')
    else:
        if bin_path.is_symlink():
            bin_path.unlink()
        bin_path.write_text('#!/bin/sh\nexec ' + shlex.join([str(python), str(repo / 't3code-customize')]) +
                            ' "$@"\n', encoding='utf-8')
        bin_path.chmod(0o755)


def write_windows_shortcut(path, repo, python, run):
    path.parent.mkdir(parents=True, exist_ok=True)
    pythonw = Path(python).with_name('pythonw.exe')
    payload = {'path': str(path), 'python': str(pythonw if pythonw.exists() else python),
               'args': subprocess.list2cmdline([str(repo / 't3code-customize'), 'launch']),
               'cwd': str(repo)}
    import base64
    data = base64.b64encode(json.dumps(payload).encode('utf-8')).decode('ascii')
    code = ("$p = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + data +
            "')) | ConvertFrom-Json; $s = (New-Object -ComObject WScript.Shell).CreateShortcut($p.path); "
            '$s.TargetPath = $p.python; $s.Arguments = $p.args; $s.WorkingDirectory = $p.cwd; $s.Save()')
    encoded = base64.b64encode(code.encode('utf-16le')).decode('ascii')
    run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded])
