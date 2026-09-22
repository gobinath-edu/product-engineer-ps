# API setup

The API uses the project's existing Python environment.

Required packages already used by the project:
- fastapi
- uvicorn
- pydantic
- sqlalchemy

Start from the project root:

```powershell
$env:PYTHONPATH=".\backend"
uvicorn app.api:app --reload --port 8000
```
