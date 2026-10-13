@echo off
REM Build Python packages from the checkout, regardless of the current folder.
pushd "%~dp0.."
python -m build
set "build_status=%errorlevel%"
popd
exit /b %build_status%
