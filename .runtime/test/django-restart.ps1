Set-Location -LiteralPath 'c:\Users\wangd\PycharmProjects\PythonProject\netops-agent\web\django_backend'
$env:DJANGO_DEBUG='true'
$env:FASTAPI_BASE_URL='http://localhost:8000'
$env:JWT_SECRET_KEY='my-secret-key-2026-netops'
if ('my-secret-key-2026-netops') { $env:SECRET_KEY='my-secret-key-2026-netops' }
& 'c:\Users\wangd\PycharmProjects\PythonProject\netops-agent\venv\Scripts\python.exe' -m daphne -b 0.0.0.0 -p 8001 django_backend.asgi:application 2>&1 | Tee-Object -FilePath 'c:\Users\wangd\PycharmProjects\PythonProject\netops-agent\.runtime\test\django.log'
