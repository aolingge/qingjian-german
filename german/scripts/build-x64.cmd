@echo off
rem x64 phase of the German Qingjian build: server + tsf + settings (one cargo invocation
rem so the three binaries link against exactly the same rlibs).
rem
rem Environment notes (this machine has no Windows SDK installed):
rem   * sdklib\<arch>  - SDK import + UCRT .lib files from the NuGet packages
rem                      Microsoft.Windows.SDK.CPP.{x64,x86} 10.0.29648.1000-preview
rem   * sdkinc        - SDK headers from the NuGet package Microsoft.Windows.SDK.CPP
rem   * sdkbin\x64    - mt.exe / rc.exe from Microsoft.Windows.SDK.BuildTools
rem                     10.0.29648.1000-preview.  Without mt.exe on PATH, linking
rem                     qingjian-settings dies with "LNK1158: cannot run mt.exe"
rem                     (windows_reactor_setup passes /MANIFEST:EMBED /MANIFESTINPUT).
rem                     sdkbin holds no .lib, so the linker cannot pick a
rem                     wrong-architecture library up from it.
rem   * LIB must contain sdklib\x64 ONLY here.  A .lib directory of the other
rem     architecture on LIB makes every x64 link fail with LNK4272
rem     "library machine type x86 conflicts with target x64".
rem
rem NB: %VC% contains "(x86)", so it can never be expanded inside an if(...) or
rem for(...) block - cmd treats the parenthesis as the end of the block.  All the
rem paths that go into LIB/INCLUDE/PATH are therefore pre-expanded into *_FULL
rem variables outside any block.
rem Usage: build-x64.cmd check | build-x64.cmd release | build-x64.cmd env
setlocal
set "SRC=C:\Users\aolin\AppData\Local\Temp\codex-qingjian-source-20260926"
set "TOOLS=E:\codemain\qingjian-de"
set "VC=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207"
set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
set "VCBIN=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64"
set "PATH=%VCBIN%;%TOOLS%\qjbin\x64;%PATH%"
call "%VCVARS%" >nul
if errorlevel 1 goto vcfailed
set "INC_FULL=%VC%\include;%TOOLS%\sdkinc\ucrt;%TOOLS%\sdkinc\shared;%TOOLS%\sdkinc\um"
set "LIB_FULL=%TOOLS%\sdklib\x64;%VC%\lib\x64"
set "INCLUDE=%INC_FULL%"
set "LIB=%LIB_FULL%"
set "QINGJIAN_UIACCESS=0"
cd /d "%SRC%"
if /i "%~1"=="env" goto env
if /i "%~1"=="check" goto check
> "%TOOLS%\x64-env.txt" echo LIB=%LIB%
>> "%TOOLS%\x64-env.txt" echo PATH=%PATH%
>> "%TOOLS%\x64-env.txt" echo CARGO_ENCODED_RUSTFLAGS=%CARGO_ENCODED_RUSTFLAGS%
>> "%TOOLS%\x64-env.txt" echo RUSTFLAGS=%RUSTFLAGS%
>> "%TOOLS%\x64-env.txt" echo LINK=%LINK%
>> "%TOOLS%\x64-env.txt" echo LIBPATH=%LIBPATH%
>> "%TOOLS%\x64-env.txt" echo LIB_FULL=%LIB_FULL%
>> "%TOOLS%\x64-env.txt" echo VCBIN=%VCBIN%
>> "%TOOLS%\x64-env.txt" echo PROBE1=%TOOLS%\sdklib\x64
>> "%TOOLS%\x64-env.txt" echo TARGET=%CARGO_BUILD_TARGET%
cargo build -v --release --locked -p qingjian-windows-server -p qingjian-windows-tsf -p qingjian-windows-settings
exit /b %errorlevel%
:check
cargo check --release --locked -p qingjian-windows-server -p qingjian-windows-tsf -p qingjian-windows-settings
exit /b %errorlevel%
:env
echo LIB=%LIB_FULL%
echo INCLUDE=%INC_FULL%
exit /b 0
:vcfailed
echo vcvars64 failed
exit /b 1
