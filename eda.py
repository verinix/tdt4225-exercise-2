import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
import matplotlib.pyplot as plt
from haversine import haversine

DATASET_PATH = Path(__file__).parent / "data" / "porto.csv"
MIN_VALID_POINTS = 3
DENSITY_SAMPLE_RATE = 0.01
TRAJECTORY_SAMPLE_RATE = 0.0001
RANDOM_SEED = 42

def percentile_from_counts(counter, percentile):
    target = sum(counter.values()) * percentile
    cumulative = 0

    for value, count in sorted(counter.items()):
        cumulative += count
        if cumulative >= target:
            return value

def analyze_dataset():
    trip_count = 0
    total_point_count = 0

    taxi_ids = set()
    trip_ids = set()
    duplicate_ids = set()

    call_type_counts = Counter()
    day_type_counts = Counter()
    trajectory_length_counts = Counter()
    trajectory_quality_counts = Counter()

    with DATASET_PATH.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            trip_count += 1
            trip_id = row["TRIP_ID"]

            if trip_id in trip_ids:
                duplicate_ids.add(trip_id)

            trip_ids.add(trip_id)
            taxi_ids.add(row["TAXI_ID"])

            call_type_counts[row["CALL_TYPE"]] += 1
            day_type_counts[row["DAY_TYPE"]] += 1

            points = json.loads(row["POLYLINE"])
            point_count = len(points)
            is_invalid = point_count < MIN_VALID_POINTS

            trajectory_length_counts[point_count] += 1
            trajectory_quality_counts[(row["MISSING_DATA"], is_invalid)] += 1
            total_point_count += point_count

    invalid_trips = trajectory_length_counts[0] + trajectory_length_counts[1] + trajectory_length_counts[2]

    print("Dataset")
    print(f"Trips: {trip_count:,}")
    print(f"Distinct taxis: {len(taxi_ids):,}")
    print(f"GPS observations: {total_point_count:,}")

    print("\nCall types")
    for call_type, count in sorted(call_type_counts.items()):
        print(f"{call_type}: {count:,}")

    print("\nDay types")
    for day_type, count in sorted(day_type_counts.items()):
        print(f"{day_type}: {count:,}")

    print("\nTrajectory quality")
    print(f"Empty trajectories: {trajectory_length_counts[0]:,}")
    print(f"Invalid trips: {invalid_trips:,}")

    print("\nMissing data and trip validity")
    for missing in ("False", "True"):
        valid = trajectory_quality_counts[(missing, False)]
        invalid = trajectory_quality_counts[(missing, True)]
        print(f"MISSING_DATA={missing}: {valid:,} valid, {invalid:,} invalid")

    print("\nTrajectory length distribution")
    print(f"Average: {total_point_count / trip_count:.2f} points")
    print(f"Median: {percentile_from_counts(trajectory_length_counts, 0.5)} points")
    print(f"95th percentile: {percentile_from_counts(trajectory_length_counts, 0.95)} points")
    print(f"99th percentile: {percentile_from_counts(trajectory_length_counts, 0.99)} points")
    print(f"Maximum: {max(trajectory_length_counts)} points")

    return duplicate_ids, trajectory_length_counts

def analyze_duplicates(duplicate_ids):
    records_by_id = defaultdict(list)
    
    with DATASET_PATH.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            trip_id = row["TRIP_ID"]
            if trip_id in duplicate_ids:
                records_by_id[trip_id].append(row)

    identical_id_count = 0
    conflicting_id_count = 0

    for records in records_by_id.values():
        first_record = records[0]
        identical = True

        for record in records[1:]:
            if record != first_record:
                identical = False
                break

        if identical:
            identical_id_count += 1
        else:
            conflicting_id_count += 1

    print("\nDuplicate trip IDs")
    print(f"Duplicated IDs: {len(duplicate_ids):,}")
    print(f"Identical: {identical_id_count:,}")
    print(f"Conflicting: {conflicting_id_count:,}")

def plot_trajectory_lengths(trajectory_lengths):
    p99_length = percentile_from_counts(trajectory_lengths, 0.99)
    lengths = []
    counts = []

    for length, count in sorted(trajectory_lengths.items()):
        if length <= p99_length:
            lengths.append(length)
            counts.append(count)

    plt.figure(figsize=(8, 5))
    plt.hist(lengths, bins=40, weights=counts)
    plt.xlabel("GPS points per trip")
    plt.ylabel("Number of trips")
    plt.title("Trajectory length distribution (up to the 99th percentile)")
    plt.show()

def sample_spatial_data():
    rng = random.Random(RANDOM_SEED)
    sampled_points = []
    sampled_trajectories = []

    with DATASET_PATH.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            points = json.loads(row["POLYLINE"])

            if not points:
                continue

            if rng.random() < DENSITY_SAMPLE_RATE:
                sampled_points.extend(points)

            if len(points) >= MIN_VALID_POINTS and rng.random() < TRAJECTORY_SAMPLE_RATE:
                sampled_trajectories.append(points)

    return sampled_points, sampled_trajectories

def plot_spatial_density(points):
    longitudes = [point[0] for point in points]
    latitudes = [point[1] for point in points]

    plt.figure(figsize=(8, 7))
    density = plt.hexbin(longitudes, latitudes, bins="log", mincnt=1)
    plt.colorbar(density, label="Sampled GPS observations per cell")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title("Spatial density of GPS observations")
    plt.show()

def plot_sampled_trajectories(trajectories):
    plt.figure(figsize=(8, 7))

    for points in trajectories:
        longitudes = [point[0] for point in points]
        latitudes = [point[1] for point in points]
        plt.plot(longitudes, latitudes, linewidth=0.7, alpha=0.15)

    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title(f"Sample of {len(trajectories)} trajectories")
    plt.show()

def analyze_spatial_jumps():
    thresholds = (0.5, 1, 2)
    trips_above_threshold = Counter()
    analyzed_trip_count = 0

    with DATASET_PATH.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            points = json.loads(row["POLYLINE"])

            if row["MISSING_DATA"] != "False" or len(points) < MIN_VALID_POINTS:
                continue

            analyzed_trip_count += 1
            max_jump_km = 0.0

            for index in range(len(points) - 1):
                lon1, lat1 = points[index]
                lon2, lat2 = points[index + 1]

                distance_km = haversine((lat1, lon1), (lat2, lon2))

                if distance_km > max_jump_km:
                    max_jump_km = distance_km

            for threshold in thresholds:
                if max_jump_km > threshold:
                    trips_above_threshold[threshold] += 1

    print("\nValid trips containing large GPS jumps")
    for threshold in thresholds:
        count = trips_above_threshold[threshold]
        percentage = count / analyzed_trip_count * 100
        print(f"{threshold} km: {count:,} trips ({percentage:.2f}%)")

def main():
    duplicate_ids, trajectory_lengths = analyze_dataset()
    analyze_duplicates(duplicate_ids)

    plot_trajectory_lengths(trajectory_lengths)

    sampled_points, sampled_trajectories = sample_spatial_data()
    plot_spatial_density(sampled_points)
    plot_sampled_trajectories(sampled_trajectories)

    analyze_spatial_jumps()

if __name__ == "__main__":
    main()
