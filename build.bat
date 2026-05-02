@echo off
REM musren Build Script

echo Building musren...
python -m build

for %%i in (dist\musren-*.whl) do (
    echo Installing %%i...
    pip install "%%i"
)

echo.
echo musren installed! Run 'python app.py' to start.