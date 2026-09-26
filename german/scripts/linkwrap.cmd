@echo off
rem Linker shim for the German Qingjian build on this machine (no Windows SDK installed;
rem import libs come from E:\codemain\qingjian-de\sdklib\<arch>, see build-x64.cmd).
rem Same link.exe as the default, but started from here instead of resolved through PATH.
rem NO parenthesised ( ) blocks below: %LIB% contains "(x86)" and inside a block cmd
rem ends the block at that ")" and dies with "\Microsoft was unexpected at this time.".
set "LINK_EXE=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207\bin\HostX64\x64\link.exe"
if not defined QJ_LINKLOG goto run
echo ======== >> "E:\codemain\qingjian-de\linkwrap.log"
echo LIB=%LIB% >> "E:\codemain\qingjian-de\linkwrap.log"
echo LIBPATH=%LIBPATH% >> "E:\codemain\qingjian-de\linkwrap.log"
echo ARGS=%* >> "E:\codemain\qingjian-de\linkwrap.log"
:run
"%LINK_EXE%" %*
exit /b %errorlevel%