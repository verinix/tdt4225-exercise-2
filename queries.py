from collections import defaultdict
from datetime import timedelta
from tabulate import tabulate
from DbConnector import DbConnector

SAMPLE_INTERVAL_SECONDS = 15
MIN_VALID_POINTS = 3
MAX_RELIABLE_JUMP_KM = 1
CITY_HALL_LONGITUDE = -8.62911
CITY_HALL_LATITUDE = 41.15794

def task_1(cursor):
    cursor.execute("SELECT COUNT(DISTINCT taxi_id) FROM trip")
    taxi_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM trip")
    trip_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM trajectory_point")
    point_count = cursor.fetchone()[0]

    rows = [("Taxis", taxi_count), ("Trips", trip_count), ("GPS points", point_count)]
    
    print("\nTask 1")
    print(tabulate(rows, headers=["Measure", "Count"]))

def task_2(cursor):
    query = """
    SELECT COUNT(*) / COUNT(DISTINCT taxi_id)
    FROM trip
    """

    cursor.execute(query)
    average_trips = cursor.fetchone()[0]

    print("\nTask 2")
    print(f"Average trips per taxi: {average_trips:.2f}")

def task_3(cursor):
    query = """
    SELECT taxi_id, COUNT(*) AS trip_count
    FROM trip
    GROUP BY taxi_id
    ORDER BY trip_count DESC
    LIMIT 20
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    print("\nTask 3")
    print(tabulate(rows, headers=["taxi_id", "trip_count"]))

def task_4a(cursor):
    query = """
    SELECT taxi_id, call_type, COUNT(*) AS trip_count
    FROM trip
    GROUP BY taxi_id, call_type
    ORDER BY taxi_id, trip_count DESC 
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    most_used = []
    current_taxi = None
    highest_count = None

    for taxi_id, call_type, trip_count in rows:
        if taxi_id != current_taxi:
            current_taxi = taxi_id
            highest_count = trip_count
            most_used.append((taxi_id, call_type, trip_count))
        elif trip_count == highest_count:
            most_used.append((taxi_id, call_type, trip_count))

    print("\nTask 4a")
    print(tabulate(most_used[:20], headers=["taxi_id", "call_type", "trip_count"], floatfmt=".2f"))
    if len(most_used) > 20:
        print("Showing first 20 taxis.")

def task_4b(cursor):
    averages_query = """
    SELECT
        call_type,
        AVG(%s * (point_count - 1)) / 60 AS avg_duration_min,
        AVG(distance_km) AS avg_distance_km
    FROM trip
    WHERE point_count >= %s
        AND missing_data = FALSE
        AND max_jump_km <= %s
    GROUP BY call_type
    ORDER BY call_type
    """

    cursor.execute(averages_query, (SAMPLE_INTERVAL_SECONDS, MIN_VALID_POINTS, MAX_RELIABLE_JUMP_KM))
    average_rows = cursor.fetchall()

    averages = {}
    for call_type, avg_duration, avg_distance in average_rows:
        averages[call_type] = (avg_duration, avg_distance)

    bands_query = """
    SELECT
        call_type,
        HOUR(start_time) AS start_hour,
        COUNT(*) AS trip_count
    FROM trip
    GROUP BY call_type, HOUR(start_time)
    ORDER BY call_type, start_hour
    """

    cursor.execute(bands_query)
    band_rows = cursor.fetchall()

    band_counts = defaultdict(lambda: [0, 0, 0, 0])

    for call_type, start_hour, trip_count in band_rows:
        band = start_hour // 6
        band_counts[call_type][band] += trip_count

    result = []

    for call_type in sorted(averages):
        avg_duration, avg_distance = averages[call_type]
        counts = band_counts[call_type]
        total = sum(counts)

        shares = []
        for count in counts:
            shares.append(count / total * 100)

        result.append((
            call_type,
            avg_duration,
            avg_distance,
            shares[0],
            shares[1],
            shares[2],
            shares[3]
        ))

    print("\nTask 4b")
    print(tabulate(
        result, 
        headers=[
            "call_type",
            "avg_duration_min",
            "avg_distance_km",
            "00-06 %",
            "06-12 %",
            "12-18 %",
            "18-24 %"
        ], 
        floatfmt=".2f"
    ))

def task_5(cursor):
    query = """
    SELECT
        taxi_id,
        SUM(%s * (point_count - 1)) / 3600 AS total_hours,
        SUM(distance_km) AS total_distance_km
    FROM trip
    WHERE point_count >= %s
        AND missing_data = FALSE
        AND max_jump_km <= %s
    GROUP BY taxi_id
    ORDER BY total_hours DESC
    """

    cursor.execute(query, (SAMPLE_INTERVAL_SECONDS, MIN_VALID_POINTS, MAX_RELIABLE_JUMP_KM))
    rows = cursor.fetchall()

    print("\nTask 5")
    print(tabulate(rows[:20], headers=["taxi_id", "total_hours", "total_distance_km"], floatfmt=".2f"))
    if len(rows) > 20:
        print("Showing first 20 taxis.")
    

def task_6(cursor):
    query = """
    SELECT DISTINCT trip_id
    FROM trajectory_point
    WHERE ST_Distance_Sphere(
        POINT(longitude, latitude),
        POINT(%s, %s)
    ) <= 100
    """

    cursor.execute(query, (CITY_HALL_LONGITUDE, CITY_HALL_LATITUDE))
    rows = cursor.fetchall()

    print("\nTask 6: trips within 100 m of Porto City Hall")
    print(f"Trips found: {len(rows):,}")
    print(tabulate(rows[:20], headers=["trip_id"]))
    if len(rows) > 20:
        print("Showing first 20 trips.")

def task_7(cursor):
    query = """
    SELECT COUNT(*)
    FROM trip
    WHERE point_count < %s
    """

    cursor.execute(query, (MIN_VALID_POINTS,))
    invalid_trip_count = cursor.fetchone()[0]

    print("\nTask 7")
    print(f"Invalid trips: {invalid_trip_count:,}")

def task_8(cursor):
    query = """
    SELECT trip_id
    FROM trip
    WHERE point_count >= %s
        AND missing_data = FALSE
        AND DATE(
            TIMESTAMPADD(
                SECOND,
                %s * (point_count - 1),
                start_time
            )
        ) > DATE(start_time)
    """

    cursor.execute(query, (MIN_VALID_POINTS, SAMPLE_INTERVAL_SECONDS))
    rows = cursor.fetchall()

    print("\nTask 8: midnight crossers")
    print(f"Trips found: {len(rows):,}")
    print(tabulate(rows[:20], headers=["trip_id"]))
    if len(rows) > 20:
        print("Showing first 20 trips.")

def task_9(cursor):
    query = """
    SELECT t.trip_id
    FROM trip AS t
    JOIN trajectory_point AS start_point
        ON start_point.trip_id = t.trip_id
        AND start_point.point_index = 0
    JOIN trajectory_point AS end_point
        ON end_point.trip_id = t.trip_id
        AND end_point.point_index = t.point_count - 1
    WHERE t.point_count >= %s
        AND ST_Distance_Sphere(
            POINT(start_point.longitude, start_point.latitude),
            POINT(end_point.longitude, end_point.latitude)
        ) <= 50
    """

    cursor.execute(query, (MIN_VALID_POINTS,))
    rows = cursor.fetchall()

    print("\nTask 9: circular trips")
    print(f"Trips found: {len(rows):,}")
    print(tabulate(rows[:20], headers=["trip_id"]))
    if len(rows) > 20:
        print("Showing first 20 trips.")

def task_10(cursor):
    query = """
    SELECT taxi_id, start_time, point_count, missing_data
    FROM trip
    ORDER BY taxi_id, start_time
    """

    cursor.execute(query)

    idle_totals = defaultdict(float)
    idle_counts = defaultdict(int)
    previous_trip = {}

    for taxi_id, start_time, point_count, missing_data in cursor:
        if taxi_id in previous_trip:
            previous_start, previous_point_count, previous_missing = previous_trip[taxi_id]

            if previous_point_count >= MIN_VALID_POINTS and not previous_missing:
                previous_end = previous_start + timedelta(seconds=SAMPLE_INTERVAL_SECONDS * (previous_point_count - 1))

                idle_seconds = (start_time - previous_end).total_seconds()

                if idle_seconds >= 0:
                    idle_totals[taxi_id] += idle_seconds
                    idle_counts[taxi_id] += 1

        previous_trip[taxi_id] = (start_time, point_count, missing_data)

    averages = []

    for taxi_id in idle_totals:
        average_hours = idle_totals[taxi_id] / idle_counts[taxi_id] / 3600
        averages.append((taxi_id, average_hours))

    averages.sort(key=lambda row: row[1], reverse=True)
    top_20 = averages[:20]

    print("\nTask 10")
    print(tabulate(top_20, headers=["taxi_id", "avg_idle_hours"], floatfmt=".2f"))

def main():
    database = DbConnector()

    try:
        task_1(database.cursor)
        task_2(database.cursor)
        task_3(database.cursor)
        task_4a(database.cursor)
        task_4b(database.cursor)
        task_5(database.cursor)
        task_6(database.cursor)
        task_7(database.cursor)
        task_8(database.cursor)
        task_9(database.cursor)
        task_10(database.cursor)
    finally:
        database.close_connection()

if __name__ == "__main__":
    main()
