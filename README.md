# TDT4225 Exercise 2

Python and MySQL implementation of Exercise 2.

## Setup

Requires Python 3.12 and Docker.

Create a virtual environment and install the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure the database passwords.

Start MySQL:

```powershell
docker compose up -d
```

Place the Porto Taxi Trajectory dataset in `data/`.
