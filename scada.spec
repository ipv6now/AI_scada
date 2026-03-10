# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(
    ['run_scada.py'],
    pathex=['.'],
    binaries=[
        ('C:\\Users\\TUX\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\snap7\\lib\\snap7.dll', 'snap7/lib'),
    ],
    datas=[
        ('scada_app/resources/icons', 'scada_app/resources/icons'),
    ],
    hiddenimports=[
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtNetwork',
        'pymodbus.client',
        'pymodbus.server',
        'pymodbus.payload',
        'pymodbus.datastore',
        'opcua',
        'opcua.client',
        'opcua.server',
        'snap7',
        'snap7.client',
        'snap7.common',
        'snap7.error',
        'snap7.partner',
        'snap7.protocol',
        'snap7.type',
        'sqlite3',
        'datetime',
        'time',
        'threading',
        'json',
        'csv',
        'os',
        'sys',
        'logging',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SCADA_HMI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,

)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SCADA_HMI',
)
