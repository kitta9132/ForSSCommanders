# MIT License -- map/world calibration tests, independent of the game API.
import json
import math
import random


def test_observe_returns_the_same_diagnostics_as_snapshot():
    calibration = M.MapCalibration()
    for index in range(5):
        returned = calibration.observe(
            [(.1 + index * .15, .2 + index * .1,
              100.0 + index * 20.0, -50.0 + index * 15.0)], index + 1.0)
        assert returned == calibration.snapshot()


def test_extreme_finite_world_coordinates_are_ignored():
    calibration = M.MapCalibration()
    calibration.observe([(.1, .1, 1e308, -1e308), (.2, .2, -1e308, 1e308)], 1.)
    assert calibration.snapshot()['sampleCount'] == 0


def test_identical_samples_do_not_repeat_expensive_fit():
    calibration = M.MapCalibration()
    calls = []
    original = calibration._try_fit
    def fitted():
        calls.append(1)
        original()
    calibration._try_fit = fitted
    for now in range(10):
        calibration.observe([(.5, .5, 0., 0.)], float(now))
    assert len(calls) == 1
import os
import sys


MOD_DIR = os.path.join(
    os.path.dirname(__file__), "..", "res_mods", "PnFMods", "WowsExtractor")
sys.path.insert(0, MOD_DIR)

import map_calibration as M  # noqa: E402


TURNING_ROUTE = [
    (0.12, 0.15), (0.28, 0.16), (0.43, 0.18), (0.55, 0.27),
    (0.64, 0.42), (0.62, 0.58), (0.48, 0.69), (0.31, 0.70),
    (0.18, 0.61), (0.14, 0.43), (0.24, 0.31), (0.42, 0.35),
    (0.57, 0.49), (0.46, 0.61), (0.29, 0.54), (0.19, 0.37),
    (0.35, 0.22), (0.56, 0.33), (0.66, 0.52), (0.47, 0.72),
    (0.27, 0.64), (0.11, 0.48), (0.34, 0.41), (0.53, 0.57),
    (0.38, 0.66),
]


def _world_a(nx, ny):
    return 1200.0 * nx - 600.0, -900.0 * ny + 450.0


def _world_b(nx, ny):
    return 800.0 * ny - 300.0, -700.0 * nx + 350.0


def _assert_close(left, right, tolerance=1.0e-5):
    assert abs(left - right) <= tolerance


def test_temporal_single_ship_turning_route_calibrates_axis_a_and_converts_both_ways():
    calibration = M.MapCalibration()
    for index, (nx, ny) in enumerate(TURNING_ROUTE):
        wx, wz = _world_a(nx, ny)
        snapshot = calibration.observe([(nx, ny, wx, wz)], index + 1.0)

    assert snapshot["status"] == "available"
    assert snapshot["source"] == "temporal_map_fit"
    assert snapshot["coordinateUnit"] == "game_world"
    assert snapshot["inferred"] is True
    assert snapshot["coefficients"]["axis"] == "A"
    predicted = calibration.map_to_world(0.39, 0.47)
    _assert_close(predicted[0], _world_a(0.39, 0.47)[0])
    _assert_close(predicted[2], _world_a(0.39, 0.47)[1])
    inverse = calibration.world_to_map(predicted[0], predicted[2])
    _assert_close(inverse[0], 0.39)
    _assert_close(inverse[1], 0.47)
    assert predicted[1] == 0


def test_swapped_axis_model_b_is_selected():
    calibration = M.MapCalibration()
    for index, (nx, ny) in enumerate(TURNING_ROUTE):
        wx, wz = _world_b(nx, ny)
        snapshot = calibration.observe([(nx, ny, wx, wz)], index + 1.0)
    assert snapshot["status"] == "available"
    assert snapshot["coefficients"]["axis"] == "B"
    assert snapshot["coefficients"]["worldX"]["mapAxis"] == "ny"
    assert snapshot["coefficients"]["worldZ"]["mapAxis"] == "nx"
    point = calibration.map_to_world(0.23, 0.61)
    _assert_close(point[0], _world_b(0.23, 0.61)[0])
    _assert_close(point[2], _world_b(0.23, 0.61)[1])


def test_multiple_ships_in_one_observation_can_calibrate():
    calibration = M.MapCalibration()
    for batch_index in range(0, len(TURNING_ROUTE), 3):
        batch = []
        for nx, ny in TURNING_ROUTE[batch_index:batch_index + 3]:
            wx, wz = _world_a(nx, ny)
            batch.append((nx, ny, wx, wz))
        snapshot = calibration.observe(batch, batch_index + 1.0)
    assert snapshot["status"] == "available"
    assert snapshot["sampleCount"] >= 8


def test_stationary_repeated_observations_do_not_calibrate_or_fill_reservoir():
    calibration = M.MapCalibration()
    for index in range(100):
        snapshot = calibration.observe([(0.5, 0.5, 20.0, -30.0)], index + 1.0)
    assert snapshot["status"] == "collecting"
    assert snapshot["sampleCount"] == 1
    assert calibration.map_to_world(0.5, 0.5) is None


def test_collinear_samples_are_degenerate_even_with_large_spans():
    calibration = M.MapCalibration()
    for index in range(12):
        value = 0.1 + index * 0.065
        calibration.observe([(value, value, 1000.0 * value, -800.0 * value)],
                            index + 1.0)
    snapshot = calibration.snapshot()
    assert snapshot["sampleCount"] >= 8
    assert snapshot["status"] == "degenerate"
    assert calibration.map_to_world(0.4, 0.5) is None


def test_nearly_straight_path_is_not_mistaken_for_two_dimensional_coverage():
    calibration = M.MapCalibration()
    for index in range(20):
        nx = 0.1 + index * 0.04
        ny = 0.15 + 0.7 * nx + 0.015 * math.sin(index * 0.7)
        wx, wz = _world_a(nx, ny)
        calibration.observe([(nx, ny, wx, wz)], index + 1.0)
    snapshot = calibration.snapshot()
    assert snapshot["span"]["mapY"] > 0.01
    assert snapshot["status"] == "degenerate"


def test_single_map_axis_span_is_degenerate():
    calibration = M.MapCalibration()
    for index in range(12):
        nx = 0.1 + index * 0.065
        ny = 0.5
        wx, wz = _world_a(nx, ny)
        calibration.observe([(nx, ny, wx, wz)], index + 1.0)
    assert calibration.snapshot()["status"] == "degenerate"


def test_near_repeated_micro_motion_is_suppressed():
    calibration = M.MapCalibration()
    for index in range(20):
        delta = index * 0.00001
        calibration.observe([(0.5 + delta, 0.5 + delta,
                             100.0 + delta, 200.0 + delta)], index + 1.0)
    assert calibration.snapshot()["sampleCount"] == 1


def test_non_finite_and_out_of_domain_inputs_are_ignored_and_snapshot_is_json_safe():
    calibration = M.MapCalibration()
    calibration.observe([
        (float("nan"), 0.2, 1.0, 2.0),
        (0.2, float("inf"), 1.0, 2.0),
        (0.2, 0.3, float("-inf"), 2.0),
        (-0.1, 0.4, 1.0, 2.0),
    ], 1.0)
    assert calibration.snapshot()["sampleCount"] == 0
    snapshot = calibration.observe([(0.2, 0.3, 1.0, 2.0)], 2.0)
    json.dumps(snapshot, allow_nan=False)
    assert snapshot["sampleCount"] == 1
    assert calibration.map_to_world(float("nan"), 0.5) is None
    assert calibration.world_to_map(1.0, float("inf")) is None


def test_heldout_outlier_is_rejected_then_does_not_freeze_future_clean_fit():
    calibration = M.MapCalibration()
    route = list(TURNING_ROUTE)
    nx, ny = route[0]
    wx, wz = _world_a(nx, ny)
    route[0] = (nx, ny, wx + 500.0, wz - 500.0)
    for index, point in enumerate(route[:8]):
        if len(point) == 2:
            nx, ny = point
            wx, wz = _world_a(nx, ny)
        else:
            nx, ny, wx, wz = point
        snapshot = calibration.observe([(nx, ny, wx, wz)], index + 1.0)
    assert snapshot["status"] == "rejected"
    assert calibration.map_to_world(0.4, 0.4) is None

    for index, (nx, ny) in enumerate(TURNING_ROUTE[8:], 8):
        wx, wz = _world_a(nx, ny)
        snapshot = calibration.observe([(nx, ny, wx, wz)], index + 1.0)
    assert snapshot["status"] == "available"
    assert snapshot["holdoutOutlierCount"] == 1


def test_available_coefficients_remain_stable_and_reservoir_is_bounded():
    calibration = M.MapCalibration()
    for index, (nx, ny) in enumerate(TURNING_ROUTE):
        wx, wz = _world_a(nx, ny)
        calibration.observe([(nx, ny, wx, wz)], index + 1.0)
    assert calibration.snapshot()["status"] == "available"
    coefficients = calibration.snapshot()["coefficients"]

    for index in range(400):
        nx = ((index * 37) % 997) / 997.0
        ny = ((index * 113 + 23) % 991) / 991.0
        wx, wz = _world_a(nx, ny)
        snapshot = calibration.observe([(nx, ny, wx, wz)], 100.0 + index)
    assert snapshot["sampleCount"] <= 256
    assert snapshot["coefficients"] == coefficients


def test_clear_and_time_reversal_reset_calibration_epoch():
    calibration = M.MapCalibration()
    for index, (nx, ny) in enumerate(TURNING_ROUTE):
        wx, wz = _world_a(nx, ny)
        calibration.observe([(nx, ny, wx, wz)], index + 10.0)
    assert calibration.snapshot()["status"] == "available"

    calibration.clear()
    assert calibration.snapshot()["status"] == "collecting"
    assert calibration.snapshot()["sampleCount"] == 0

    for index, (nx, ny) in enumerate(TURNING_ROUTE):
        wx, wz = _world_a(nx, ny)
        calibration.observe([(nx, ny, wx, wz)], index + 100.0)
    assert calibration.snapshot()["status"] == "available"
    snapshot = calibration.observe([(0.24, 0.31) + _world_a(0.24, 0.31)], 1.0)
    assert snapshot["status"] == "collecting"
    assert snapshot["sampleCount"] == 1
    assert calibration.map_to_world(0.4, 0.4) is None


def test_three_consecutive_drift_batches_invalidate_frozen_coefficients():
    calibration = M.MapCalibration()
    for index, (nx, ny) in enumerate(TURNING_ROUTE):
        wx, wz = _world_a(nx, ny)
        calibration.observe([(nx, ny, wx, wz)], index + 1.0)
    assert calibration.snapshot()["status"] == "available"

    for index, (nx, ny) in enumerate(((0.22, 0.25), (0.49, 0.32), (0.61, 0.63))):
        wx, wz = _world_a(nx, ny)
        calibration.observe([(nx, ny, wx + 200.0, wz - 200.0)],
                            100.0 + index)
    snapshot = calibration.snapshot()
    assert snapshot["status"] == "collecting"
    assert snapshot["sampleCount"] == 1
    assert snapshot["coefficients"] is None
    assert calibration.map_to_world(0.4, 0.4) is None


def test_inverse_rejects_world_locations_outside_normalized_map():
    calibration = M.MapCalibration()
    for index, (nx, ny) in enumerate(TURNING_ROUTE):
        wx, wz = _world_a(nx, ny)
        calibration.observe([(nx, ny, wx, wz)], index + 1.0)
    assert calibration.world_to_map(-10000.0, -10000.0) is None


class _BruteForceCalibration(M.MapCalibration):
    """Reference duplicate predicate retained for exact behavior comparisons."""
    def _is_duplicate(self, values):
        for item in self._samples:
            old = item["v"]
            map_distance = math.sqrt((values[0] - old[0]) ** 2 +
                                     (values[1] - old[1]) ** 2)
            world_distance = math.sqrt((values[2] - old[2]) ** 2 +
                                       (values[3] - old[3]) ** 2)
            if (map_distance <= M._MAP_DUPLICATE_DISTANCE and
                    world_distance <= M._WORLD_DUPLICATE_DISTANCE):
                return True
        return False


def _assert_duplicate_index_consistent(calibration):
    indexed_slots = []
    assert len(calibration._duplicate_buckets) <= len(calibration._samples)
    for key, slots in calibration._duplicate_buckets.items():
        assert slots
        assert len(slots) == len(set(slots))
        for slot in slots:
            assert 0 <= slot < len(calibration._samples)
            assert calibration._duplicate_bucket_key(
                calibration._samples[slot]["v"]) == key
            indexed_slots.append(slot)
    assert sorted(indexed_slots) == list(range(len(calibration._samples)))


def _assert_matches_brute_force(indexed, reference):
    assert indexed.snapshot() == reference.snapshot()
    assert indexed._samples == reference._samples
    assert indexed._seen == reference._seen
    assert indexed._sequence == reference._sequence
    assert indexed._rng == reference._rng
    assert indexed._last_now == reference._last_now
    assert indexed._model == reference._model
    assert indexed._status == reference._status
    assert indexed._reason == reference._reason
    _assert_duplicate_index_consistent(indexed)


def test_spatial_index_matches_brute_force_through_full_reservoir_and_resets():
    indexed = M.MapCalibration()
    reference = _BruteForceCalibration()

    def observe(batch, now):
        left = indexed.observe(batch, now)
        right = reference.observe(batch, now)
        assert left == right
        _assert_matches_brute_force(indexed, reference)
        return left

    for index, (nx, ny) in enumerate(TURNING_ROUTE):
        wx, wz = _world_a(nx, ny)
        observe([(nx, ny, wx, wz)], index + 1.0)

    rng = random.Random(43044)
    for index in range(1500):
        if index % 5 == 0 and indexed._samples:
            old = indexed._samples[rng.randrange(len(indexed._samples))]["v"]
            nx = min(1.0, max(0.0, old[0] + rng.uniform(-0.001, 0.001)))
            ny = min(1.0, max(0.0, old[1] + rng.uniform(-0.001, 0.001)))
        else:
            nx = rng.random()
            ny = rng.random()
        wx, wz = _world_a(nx, ny)
        observe([(nx, ny, wx, wz)], 100.0 + index)

    assert len(indexed._samples) == M._MAX_SAMPLES
    assert indexed._seen > M._MAX_SAMPLES
    assert max(item["seq"] for item in indexed._samples) > M._MAX_SAMPLES

    # Three majority-outlier batches exercise the frozen-fit drift reset.
    for index, (nx, ny) in enumerate(TURNING_ROUTE[:6]):
        wx, wz = _world_a(nx, ny)
        observe([(nx, ny, wx + 500.0, wz - 500.0)], 2000.0 + index)
    for index, (nx, ny) in enumerate(TURNING_ROUTE[6:12]):
        wx, wz = _world_a(nx, ny)
        observe([(nx, ny, wx + 500.0, wz - 500.0)], 2010.0 + index)
    for index, (nx, ny) in enumerate(TURNING_ROUTE[12:18]):
        wx, wz = _world_a(nx, ny)
        observe([(nx, ny, wx + 500.0, wz - 500.0)], 2020.0 + index)

    # Invalid inputs remain filtered before the index is consulted.
    observe([(float("nan"), 0.2, 1.0, 2.0),
             (0.2, float("inf"), 1.0, 2.0),
             (-0.1, 0.4, 1.0, 2.0),
             (0.2, 0.3, 1.0e308, 2.0)], 2030.0)

    # A backwards timestamp clears both the reservoir and its index.
    observe([TURNING_ROUTE[0] + _world_a(*TURNING_ROUTE[0])], 1.0)
    assert len(indexed._samples) == 1
    assert len(indexed._duplicate_buckets) == 1
    indexed.clear()
    reference.clear()
    _assert_matches_brute_force(indexed, reference)
    assert indexed._duplicate_buckets == {}


def test_spatial_index_covers_float_bucket_and_duplicate_threshold_boundaries():
    cell = M._MAP_DUPLICATE_BUCKET_SIZE
    radius = M._MAP_DUPLICATE_DISTANCE
    nextafter = getattr(math, "nextafter", None)
    boundaries = [index * cell for index in range(126)]
    if nextafter is not None:
        for boundary in list(boundaries):
            boundaries.extend((nextafter(boundary, -float("inf")),
                               nextafter(boundary, float("inf"))))

    map_offsets = ((radius, 0.0), (-radius, 0.0),
                   (0.0, radius), (0.0, -radius),
                   (radius * 0.7, radius * 0.7),
                   (radius * 0.8, radius * 0.8),
                   (nextafter(radius, 0.0) if nextafter else radius, 0.0))
    world_offsets = (0.0, 3.0, -3.0,
                     nextafter(3.0, 0.0) if nextafter else 3.0,
                     nextafter(3.0, float("inf")) if nextafter else 3.0)
    cases = []
    for x in boundaries:
        if x < 0.0 or x > 1.0:
            continue
        for y in boundaries[::17]:
            if y < 0.0 or y > 1.0:
                continue
            for dx, dy in map_offsets:
                nx, ny = x + dx, y + dy
                if nx < 0.0 or nx > 1.0 or ny < 0.0 or ny > 1.0:
                    continue
                for world_dx in world_offsets:
                    cases.append(((x, y, 100.0, 200.0),
                                  (nx, ny, 100.0 + world_dx, 200.0)))

    rng = random.Random(20261104)
    for unused in range(5000):
        x = rng.random()
        y = rng.random()
        dx = rng.uniform(-radius * 1.1, radius * 1.1)
        dy = rng.uniform(-radius * 1.1, radius * 1.1)
        nx, ny = x + dx, y + dy
        if nx < 0.0 or nx > 1.0 or ny < 0.0 or ny > 1.0:
            continue
        world_dx = rng.uniform(-3.1, 3.1)
        world_dz = rng.uniform(-3.1, 3.1)
        cases.append(((x, y, 100.0, 200.0),
                      (nx, ny, 100.0 + world_dx, 200.0 + world_dz)))

    for old_values, new_values in cases:
        indexed = M.MapCalibration()
        reference = _BruteForceCalibration()
        item = {"v": old_values, "seq": 0}
        indexed._samples.append(item)
        indexed._index_duplicate_sample(0, item)
        reference._samples.append(dict(item))
        expected = reference._is_duplicate(new_values)
        candidates = indexed._duplicate_candidate_slots(new_values)
        actual = indexed._is_duplicate(new_values)
        assert actual == expected
        if expected:
            assert 0 in candidates


def test_spatial_index_reduces_exact_distance_candidates_at_full_reservoir():
    indexed = M.MapCalibration()
    reference = _BruteForceCalibration()
    for index in range(M._MAX_SAMPLES):
        nx = ((index % 16) + 0.5) / 16.0
        ny = ((index // 16) + 0.5) / 16.0
        values = (nx, ny, 10000.0 * nx, -9000.0 * ny)
        item = {"v": values, "seq": index}
        indexed._samples.append(item)
        indexed._index_duplicate_sample(index, item)
        reference._samples.append(dict(item))

    nearby = indexed._samples[128]["v"]
    query = (nearby[0], nearby[1], 987654.0, -876543.0)
    candidates = indexed._duplicate_candidate_slots(query)
    assert len(candidates) < 32

    original_sqrt = math.sqrt
    checks = []

    def counted_sqrt(value):
        checks.append(value)
        return original_sqrt(value)

    math.sqrt = counted_sqrt
    try:
        indexed_result = indexed._is_duplicate(query)
        indexed_checks = len(checks) // 2
        checks[:] = []
        reference_result = reference._is_duplicate(query)
        reference_checks = len(checks) // 2
    finally:
        math.sqrt = original_sqrt

    assert indexed_result is reference_result
    assert indexed_checks == len(candidates)
    assert reference_checks == M._MAX_SAMPLES
    assert indexed_checks < reference_checks
    _assert_duplicate_index_consistent(indexed)
