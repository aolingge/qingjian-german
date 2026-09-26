@echo off
rem x86 phase of the German Qingjian build: the 32-bit TSF DLL only (the
rem WOW6432Node CLSID twin used by 32-bit applications).  Needs
rem `rustup target add i686-pc-windows-msvc` for the 1.96.0 toolchain; without it
rem this phase fails with "can't find crate for `core` ... the i686-pc-windows-msvc
rem target may not be installed".
rem
rem IMPORTANT: LIB must stay on the x64 dirs here.  cargo compiles build scripts and
rem proc-macros for the HOST (x86_64) and links them with this same LIB, so pointing
rem LIB at sdklib\x86 makes every host link fail with
rem   warning LNK4272: library machine type 'x86' conflicts with target machine type 'x64'
rem plus `fatal error LNK1120` for proc-macro2 / quote / serde / anyhow / ...
rem The i686 TARGET gets its x86 import libraries through the /LIBPATH link args
rem declared in the workspace .cargo\config.toml instead.
rem
rem %VC% contains "(x86)", so it can never be expanded inside an if(...) block:
rem paths are pre-expanded into *_FULL variables outside any block.
setlocal
set "SRC=C:\Users\aolin\AppData\Local\Temp\codex-qingjian-source-20260926"
set "TOOLS=E:\codemain\qingjian-de"
set "VC=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207"
set "VCBIN=%VC%\bin\Hostx64\x64"
set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
call "%VCVARS%" >nul
if errorlevel 1 goto vcfailed
set "INC_FULL=%VC%\include;%TOOLS%\sdkinc\ucrt;%TOOLS%\sdkinc\shared;%TOOLS%\sdkinc\um"
set "LIB_FULL=%TOOLS%\sdklib\x64;%VC%\lib\x64"
set "PATH=%VCBIN%;%TOOLS%\qjbin\x64;%PATH%"
set "INCLUDE=%INC_FULL%"
set "LIB=%LIB_FULL%"
set "QINGJIAN_UIACCESS=0"
cd /d "%SRC%"
cargo build --release --locked -p qingjian-windows-tsf --target i686-pc-windows-msvc
exit /b %errorlevel%
:vcfailed
echo vcvars64 failed
exit /b 1