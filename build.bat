@echo off
REM MusRen Build Script

echo Building MusRen...
python -m build

for %%i in (dist\musren-*.whl) do (
    echo Installing %%i...
    pip install "%%i"
)

echo.
echo MusRen installed! Run 'musren' to start.