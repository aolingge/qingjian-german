@echo off
rem Run unit tests for the crates touched by the German language patch.
rem Usage: test-de.cmd [extra cargo test args]
setlocal
set "SRC=C:\Users\aolin\AppData\Local\Temp\codex-qingjian-source-20260926"
set "TOOLS=E:\codemain\qingjian-de"
set "VCROOT=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207"
set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
call "%VCVARS%" >nul
if errorlevel 1 (
  echo vcvars64 failed
  exit /b 1
)
set "QINGJIAN_UIACCESS=0"
set "INCLUDE=%VCROOT%\include;%TOOLS%\sdkinc\ucrt;%TOOLS%\sdkinc\shared;%TOOLS%\sdkinc\um"
set "LIB=%TOOLS%\sdklib\x64;%VCROOT%\lib\x64"
cd /d "%SRC%"
cargo test --release --locked -p qingjian-core -p qingjian-predict %*
exit /b %errorlevel%
