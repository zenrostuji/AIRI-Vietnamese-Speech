# Optional equivalent of build-windows.bat for users who prefer a spec file.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = collect_submodules("vieneu")
datas = collect_data_files("vieneu") + [("ui", "ui")]

a = Analysis(["launcher.py"], pathex=["."], binaries=[], datas=datas,
             hiddenimports=hiddenimports, excludes=[])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas,
          name="AIRI Vietnamese Speech", console=True)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas,
               name="AIRI Vietnamese Speech")
