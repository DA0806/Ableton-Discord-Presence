"""Pure installer logic for the AbletonDiscordPresence setup wizard — no
tkinter/GUI dependency, so it's testable as a plain script. The GUI
(setup_wizard.py) only calls these functions and renders their results."""
import ctypes
import os
import shutil
import uuid

FOLDERID_DOCUMENTS = 'FDD39AD0-238F-46AF-ADB4-6C85480369C7'
REMOTE_SCRIPTS_SUBPATH = ('Ableton', 'User Library', 'Remote Scripts')
SCRIPT_FOLDER_NAME = 'AbletonDiscordPresence'


class _GUID(ctypes.Structure):
    _fields_ = [
        ('Data1', ctypes.c_uint32),
        ('Data2', ctypes.c_uint16),
        ('Data3', ctypes.c_uint16),
        ('Data4', ctypes.c_uint8 * 8),
    ]


def get_default_documents_path():
    """Real Documents folder path, resolving OneDrive Known Folder Move
    redirection via the Windows Known Folder API — more reliable than
    assuming %USERPROFILE%\\Documents."""
    try:
        guid = _GUID.from_buffer_copy(uuid.UUID(FOLDERID_DOCUMENTS).bytes_le)
        path_ptr = ctypes.c_wchar_p()
        hresult = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, 0, ctypes.byref(path_ptr))
        if hresult == 0:
            path = path_ptr.value
            ctypes.windll.ole32.CoTaskMemFree(path_ptr)
            return path
    except Exception:
        pass
    return os.path.join(os.path.expanduser('~'), 'Documents')


def get_remote_scripts_path():
    return os.path.join(get_default_documents_path(), *REMOTE_SCRIPTS_SUBPATH)


def is_existing_install(remote_scripts_path):
    return os.path.isdir(os.path.join(remote_scripts_path, SCRIPT_FOLDER_NAME))


def install(source_dir, remote_scripts_path):
    """Copy source_dir (the AbletonDiscordPresence folder) into
    remote_scripts_path, creating it if needed and overwriting any
    existing install. Returns the final destination path."""
    os.makedirs(remote_scripts_path, exist_ok=True)
    dest = os.path.join(remote_scripts_path, SCRIPT_FOLDER_NAME)
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    shutil.copytree(source_dir, dest)
    return dest


if __name__ == '__main__':
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        source = os.path.join(tmp, 'AbletonDiscordPresence')
        os.makedirs(source)
        with open(os.path.join(source, '__init__.py'), 'w') as f:
            f.write('# stub')

        remote_scripts = os.path.join(tmp, 'Remote Scripts')
        assert not is_existing_install(remote_scripts)

        dest = install(source, remote_scripts)
        assert os.path.isfile(os.path.join(dest, '__init__.py'))
        assert is_existing_install(remote_scripts)

        # Re-install must overwrite cleanly (update path), not error.
        with open(os.path.join(source, '__init__.py'), 'w') as f:
            f.write('# updated stub')
        dest2 = install(source, remote_scripts)
        with open(os.path.join(dest2, '__init__.py')) as f:
            assert f.read() == '# updated stub'

        real_path = get_default_documents_path()
        assert os.path.isdir(real_path), 'get_default_documents_path() returned a non-existent path'
        print('Detected Documents folder:', real_path)

    print('wizard_logic: all checks passed')
