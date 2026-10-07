@echo off
rem Full German-build driver: x64 trio first (must succeed), then the x86 TSF DLL.
rem Each phase runs in its own build-*.cmd so the x86 LIB/PATH can never leak into the
rem x64 link (that produced "LNK4272: library machine type x86 conflicts with target x64").
rem Usage: build-de.cmd check | build-de.cmd release
rem
rem NB: no parenthesised if-blocks anywhere in the build scripts.  %VC% contains
rem "(x86)" and cmd mis-parses the parenthesis inside a block.
setlocal
set "TOOLS=E:\codemain\qingjian-de"
if /i "%~1"=="check" goto check
call "%TOOLS%\build-x64.cmd" release
if errorlevel 1 goto x64failed
call "%TOOLS%\build-x86.cmd"
exit /b %errorlevel%
:check
call "%TOOLS%\build-x64.cmd" check
exit /b %errorlevel%
:x64failed
echo x64 phase failed, not starting the x86 phase
exit /b 1
