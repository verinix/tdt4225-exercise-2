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

Place the Porto Taxi Trajectory dataset at `data/porto.csv`.

## Part 1

Run the exploratory data analysis:

```powershell
python eda.py
```

Create the database schema, clean the data, and import it:

```powershell
python load_data.py
```

EDA figures are stored in `figures/`.

## Part 2

After importing the dataset, run the analytical queries:

```powershell
python queries.py
```

## Part 3

The report is stored in `docs/`.
