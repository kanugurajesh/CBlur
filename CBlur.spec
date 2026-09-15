from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

a = Analysis(['main.py'], pathex=[],
    binaries=collect_dynamic_libs('mediapipe'),
    datas=[('models/*.task', 'models'), ('models/*.tflite', 'models'), ('models/manifest.json', 'models')]
          + collect_data_files('mediapipe'),
    hiddenimports=['pyvirtualcam', 'pyvirtualcam._native_windows_obs', 'pyvirtualcam._native_windows_unity_capture'],
    excludes=['jax', 'jaxlib', 'pytest', 'IPython', 'tkinter'],
    hooksconfig={'matplotlib': {'backends': ['Agg']}},
    noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='CBlur', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='CBlur')
