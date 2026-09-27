import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from haversine import haversine
from DbConnector import DbConnector

DATASET_PATH = Path(__file__).parent / "data" / "porto.csv"
BATCH_SIZE = 1000

CREATE_TRIP_TABLE = """
CREATE TABLE trip (
    trip_id BIGINT UNSIGNED NOT NULL,
    taxi_id INT UNSIGNED NOT NULL,
    call_type CHAR(1) NOT NULL,
    origin_call INT UNSIGNED NULL,
    origin_stand INT UNSIGNED NULL,
    start_time DATETIME NOT NULL,
    day_type CHAR(1) NOT NULL,
    missing_data BOOLEAN NOT NULL,
    point_count SMALLINT UNSIGNED NOT NULL,
    distance_km DOUBLE NOT NULL,
    max_jump_km DOUBLE NULL,

    PRIMARY KEY (trip_id),
    CHECK (call_type IN ('A', 'B', 'C')),
    CHECK (day_type IN ('A', 'B', 'C'))
)
"""

CREATE_TRAJECTORY_POINT_TABLE = """
CREATE TABLE trajectory_point (
    trip_id BIGINT UNSIGNED NOT NULL,
    point_index SMALLINT UNSIGNED NOT NULL,
    longitude DOUBLE NOT NULL,
    latitude DOUBLE NOT NULL,

    PRIMARY KEY (trip_id, point_index),
    FOREIGN KEY (trip_id) REFERENCES trip(trip_id)
)
"""

INSERT_TRIP = """
INSERT INTO trip (
    trip_id,
    taxi_id,
    call_type,
    origin_call,
    origin_stand,
    start_time,
    day_type,
    missing_data,
    point_count,
    distance_km,
    max_jump_km
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

INSERT_POINT = """
INSERT INTO trajectory_point (
    trip_id,
    point_index,
    longitude,
    latitude
)
VALUES (%s, %s, %s, %s)
"""

def find_duplicate_ids():
    seen_ids = set()
    duplicate_ids = set()

    with DATASET_PATH.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            trip_id = int(row["TRIP_ID"])

            if trip_id in seen_ids:
                duplicate_ids.add(trip_id)

            seen_ids.add(trip_id)

    return duplicate_ids

def classify_duplicate_ids(duplicate_ids):
    records_by_id = defaultdict(list)

    with DATASET_PATH.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            trip_id = int(row["TRIP_ID"])

            if trip_id in duplicate_ids:
                records_by_id[trip_id].append(row)

    identical_ids = set()
    conflicting_ids = set()

    for trip_id, records in records_by_id.items():
        first_record = records[0]
        identical = True

        for record in records[1:]:
            if record != first_record:
                identical = False
                break

        if identical:
            identical_ids.add(trip_id)
        else:
            conflicting_ids.add(trip_id)

    return identical_ids, conflicting_ids

def parse_optional_int(value):
    if value == "":
        return None

    return int(value)

def parse_boolean(value):
    if value == "True":
        return True

    if value == "False":
        return False

    raise ValueError(f"Unexpected boolean value: {value}")

def parse_start_time(value):
    timestamp = int(value)
    start_time = datetime.fromtimestamp(timestamp, timezone.utc)
    return start_time.replace(tzinfo=None)

def calculate_trajectory_metrics(points):
    if len(points) < 2:
        return 0, None

    distance_km = 0
    max_jump_km = 0

    for index in range(len(points) - 1):
        lon1, lat1 = points[index]
        lon2, lat2 = points[index + 1]

        segment_distance_km = haversine((lat1, lon1), (lat2, lon2))

        distance_km += segment_distance_km

        if segment_distance_km > max_jump_km:
            max_jump_km = segment_distance_km

    return distance_km, max_jump_km

def recreate_tables(cursor):
    cursor.execute("DROP TABLE IF EXISTS trajectory_point")
    cursor.execute("DROP TABLE IF EXISTS trip")
    cursor.execute(CREATE_TRIP_TABLE)
    cursor.execute(CREATE_TRAJECTORY_POINT_TABLE)

def insert_batch(cursor, connection, trip_rows, point_rows):
    cursor.executemany(INSERT_TRIP, trip_rows)

    if point_rows:
        cursor.executemany(INSERT_POINT, point_rows)

    connection.commit()

def load_data(cursor, connection, identical_ids, conflicting_ids):
    kept_identical_ids = set()
    trip_rows = []
    point_rows = []

    with DATASET_PATH.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            trip_id = int(row["TRIP_ID"])

            if trip_id in conflicting_ids:
                continue

            if trip_id in identical_ids:
                if trip_id in kept_identical_ids:
                    continue

                kept_identical_ids.add(trip_id)

            points = json.loads(row["POLYLINE"])
            point_count = len(points)
            distance_km, max_jump_km = calculate_trajectory_metrics(points)

            trip_rows.append((
                trip_id,
                int(row["TAXI_ID"]),
                row["CALL_TYPE"],
                parse_optional_int(row["ORIGIN_CALL"]),
                parse_optional_int(row["ORIGIN_STAND"]),
                parse_start_time(row["TIMESTAMP"]),
                row["DAY_TYPE"],
                parse_boolean(row["MISSING_DATA"]),
                point_count,
                distance_km,
                max_jump_km
            ))

            for point_index, point in enumerate(points):
                longitude, latitude = point
                point_rows.append((
                    trip_id,
                    point_index,
                    longitude,
                    latitude
                ))

            if len(trip_rows) >= BATCH_SIZE:
                insert_batch(cursor, connection, trip_rows, point_rows)
                trip_rows = []
                point_rows = []

    if trip_rows:
        insert_batch(cursor, connection, trip_rows, point_rows)

def create_secondary_index(cursor, connection):
    cursor.execute("CREATE INDEX idx_trip_taxi_start ON trip(taxi_id, start_time)")
    connection.commit()

def main():
    duplicate_ids = find_duplicate_ids()
    identical_ids, conflicting_ids = classify_duplicate_ids(duplicate_ids)

    print("Duplicate cleaning")
    print(f"Duplicated trip IDs: {len(duplicate_ids):,}")
    print(f"Identical duplicate IDs: {len(identical_ids):,}")
    print(f"Conflicting duplicate IDs: {len(conflicting_ids):,}")

    database = DbConnector()

    try:
        recreate_tables(database.cursor)
        database.db_connection.commit()

        load_data(database.cursor, database.db_connection, identical_ids, conflicting_ids)

        create_secondary_index(database.cursor, database.db_connection)
    except Exception:
        database.db_connection.rollback()
        raise
    finally:
        database.close_connection()

if __name__ == "__main__":
    main()
