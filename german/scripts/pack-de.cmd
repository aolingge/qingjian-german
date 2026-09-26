@echo off
rem Build qingjian-dict-convert (x64, same env as build-x64.cmd). Used to pack glossary-de.tsv -> glossary-de.qj.
setlocal
set "SRC=C:\Users\aolin\AppData\Local\Temp\codex-qingjian-source-20260926"
set "TOOLS=E:\codemain\qingjian-de"
set "VC=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207"
set "VCBIN=%VC%\bin\Hostx64\x64"
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 goto vcfailed
set "INC_FULL=%VC%\include;%TOOLS%\sdkinc\ucrt;%TOOLS%\sdkinc\shared;%TOOLS%\sdkinc\um"
set "LIB_FULL=%TOOLS%\sdklib\x64;%VC%\lib\x64"
set "PATH=%VCBIN%;%TOOLS%\qjbin\x64;%PATH%"
set "INCLUDE=%INC_FULL%"
set "LIB=%LIB_FULL%"
cd /d "%SRC%"
cargo build --release --locked -p qingjian-dict-convert
exit /b %errorlevel%
:vcfailed
echo vcvars64 failed
exit /b 1
