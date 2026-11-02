# MIT License
"""Conservative map/world calibration using only Python's :mod:`math`.

The only supported transforms are the two observed axis-aligned possibilities:

* A: worldX = a*nx+b, worldZ = c*ny+d
* B: worldX = a*ny+b, worldZ = c*nx+d

Threshold rationale (all world distances are in the game's raw world units):
map spans below 0.01 are too short to distinguish motion from quantization;
each fitted world axis must span at least 10 units; normalized map covariance
must have det/(varX*varY) > 0.05 (equivalent to 1-corr**2) so a nearly straight
path cannot identify the axes. This intentionally rejects the almost-straight
paths measured in the current Ocean recordings. Fits need eight samples, at
least six training points, and two holdouts.
The 20% deterministic holdout is never used for fitting. Residual tolerance is
max(2 units, 1.5% of the observed world span): the small absolute allowance
absorbs position/update jitter, while the relative bound scales to different
maps (no map-size constant is assumed). A single gross training outlier is
removed by a Theil-Sen/MAD robust fit. A single holdout outlier blocks a small
fit; once at least four holdouts exist, it may be isolated only when the other
three or more independently validate. Coefficients must be finite and have
absolute scale in [1, 1e6] world units per normalized map unit.

Calibration coefficients are immutable once available. Three consecutive
observation batches that are predominantly inconsistent invalidate the fit;
one bad frame cannot do so. The bounded reservoir uses deterministic Algorithm
R replacement and suppresses near-identical map/world observations.
"""

import math


_MAX_SAMPLES = 256
_MIN_SAMPLES = 8
_MIN_TRAIN = 6
_MIN_MAP_SPAN = 0.01
_MIN_WORLD_SPAN = 10.0
_MIN_COVARIANCE_RATIO = 0.05
_MIN_SCALE = 1.0
_MAX_SCALE = 1000000.0
_MAX_WORLD_COORDINATE = 1000000000.0
_MAP_DUPLICATE_DISTANCE = 0.002
_WORLD_DUPLICATE_DISTANCE = 3.0
_HOLDOUT_MODULUS = 5
_DRIFT_BATCHES = 3


def _finite(value):
    try:
        return not (math.isnan(value) or math.isinf(value))
    except Exception:
        return False


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except Exception:
        return None
    if not _finite(result):
        return None
    return result


def _median(values):
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _span(values):
    if not values:
        return None
    result = max(values) - min(values)
    if not _finite(result):
        return None
    return result


def _line(points, map_index, world_index):
    """Robust Theil-Sen initial line followed by ordinary least squares."""
    ordered = sorted(points, key=lambda item: item["seq"])
    # Bound pairwise work in long battles without losing temporal coverage.
    if len(ordered) > 64:
        selected = []
        last = len(ordered) - 1
        for index in range(64):
            selected.append(ordered[int(round(index * last / 63.0))])
        ordered = selected

    slopes = []
    for left in range(len(ordered)):
        x1 = ordered[left]["v"][map_index]
        y1 = ordered[left]["v"][world_index]
        for right in range(left + 1, len(ordered)):
            x2 = ordered[right]["v"][map_index]
            delta = x2 - x1
            if abs(delta) > 1.0e-10:
                slopes.append((ordered[right]["v"][world_index] - y1) / delta)
    slope = _median(slopes)
    if slope is None or not _finite(slope):
        return None
    offsets = [item["v"][world_index] - slope * item["v"][map_index]
               for item in points]
    intercept = _median(offsets)
    if intercept is None or not _finite(intercept):
        return None
    return slope, intercept


def _least_squares(points, map_index, world_index):
    count = float(len(points))
    if count < 2.0:
        return None
    mean_x = sum(item["v"][map_index] for item in points) / count
    mean_y = sum(item["v"][world_index] for item in points) / count
    variance = sum((item["v"][map_index] - mean_x) ** 2
                   for item in points)
    if variance <= 1.0e-12:
        return None
    covariance = sum((item["v"][map_index] - mean_x) *
                     (item["v"][world_index] - mean_y)
                     for item in points)
    slope = covariance / variance
    intercept = mean_y - slope * mean_x
    if not _finite(slope) or not _finite(intercept):
        return None
    return slope, intercept


def _residual(item, coefficients, x_index, z_index):
    x = coefficients[0][0] * item["v"][x_index] + coefficients[0][1]
    z = coefficients[1][0] * item["v"][z_index] + coefficients[1][1]
    return math.hypot(item["v"][2] - x, item["v"][3] - z)


def _covariance_ratio(points):
    count = float(len(points))
    mean_x = sum(item["v"][0] for item in points) / count
    mean_y = sum(item["v"][1] for item in points) / count
    var_x = sum((item["v"][0] - mean_x) ** 2 for item in points) / count
    var_y = sum((item["v"][1] - mean_y) ** 2 for item in points) / count
    covariance = sum((item["v"][0] - mean_x) *
                     (item["v"][1] - mean_y)
                     for item in points) / count
    product = var_x * var_y
    if var_x <= 1.0e-15 or var_y <= 1.0e-15 or product <= 1.0e-30:
        return 0.0
    determinant = var_x * var_y - covariance * covariance
    # Roundoff can make a mathematically zero determinant slightly negative.
    return max(0.0, determinant) / product


def _rmse(items, coefficients, x_index, z_index):
    if not items:
        return None
    errors = []
    for item in items:
        error = _residual(item, coefficients, x_index, z_index)
        if not _finite(error):
            return None
        errors.append(error)
    scale = max(errors)
    if scale == 0.0:
        return 0.0
    normalized_squared = sum((error / scale) ** 2 for error in errors)
    return scale * math.sqrt(normalized_squared / (2.0 * len(items)))


class MapCalibration(object):
    """Accumulate observations and expose a validated A/B map transform."""

    def __init__(self):
        self.clear()

    def clear(self):
        """Reset samples, time ordering, diagnostics, and any fitted model."""
        self._samples = []
        self._seen = 0
        self._sequence = 0
        self._rng = 1
        self._last_now = None
        self._model = None
        self._status = "collecting"
        self._reason = "insufficient_samples"
        self._rmse = None
        self._holdout_rmse = None
        self._holdout_count = 0
        self._holdout_outliers = 0
        self._drift_streak = 0
        self._fit_sample_count = 0

    def _parse_samples(self, samples):
        parsed = []
        try:
            iterator = iter(samples) if samples is not None else iter(())
        except Exception:
            return parsed
        try:
            for sample in iterator:
                try:
                    values = list(sample)
                except Exception:
                    continue
                if len(values) != 4:
                    continue
                converted = [_number(value) for value in values]
                if any(value is None for value in converted):
                    continue
                nx, ny, world_x, world_z = converted
                if nx < 0.0 or nx > 1.0 or ny < 0.0 or ny > 1.0:
                    continue
                if max(abs(world_x), abs(world_z)) > _MAX_WORLD_COORDINATE:
                    continue
                parsed.append((nx, ny, world_x, world_z))
        except Exception:
            # A partially failing generator still contributes its valid prefix.
            pass
        return parsed

    def _is_duplicate(self, values):
        for item in self._samples:
            old = item["v"]
            map_distance = math.sqrt((values[0] - old[0]) ** 2 +
                                     (values[1] - old[1]) ** 2)
            world_distance = math.sqrt((values[2] - old[2]) ** 2 +
                                       (values[3] - old[3]) ** 2)
            if (map_distance <= _MAP_DUPLICATE_DISTANCE and
                    world_distance <= _WORLD_DUPLICATE_DISTANCE):
                return True
        return False

    def _append(self, values):
        if self._is_duplicate(values):
            return False
        item = {"v": values, "seq": self._sequence}
        self._sequence += 1
        self._seen += 1
        if len(self._samples) < _MAX_SAMPLES:
            self._samples.append(item)
        else:
            # Deterministic Algorithm R. This LCG is for bounded sampling only,
            # not security or cryptographic use.
            self._rng = (1103515245 * self._rng + 12345) % 2147483648
            slot = self._rng % self._seen
            if slot < _MAX_SAMPLES:
                self._samples[int(slot)] = item
        return True

    def _append_many(self, values_list):
        changed = False
        for values in values_list:
            changed = self._append(values) or changed
        return changed

    def _fit_axis_pair(self, train, x_index, z_index):
        line_x = _line(train, x_index, 2)
        line_z = _line(train, z_index, 3)
        if line_x is None or line_z is None:
            return None
        initial = (line_x, line_z)
        errors = [_residual(item, initial, x_index, z_index) for item in train]
        med = _median(errors)
        deviations = [abs(error - med) for error in errors]
        mad = _median(deviations)
        cap = max(5.0, max(_span([item["v"][2] for item in train]) or 0.0,
                           _span([item["v"][3] for item in train]) or 0.0) * 0.05)
        cutoff = min(cap, max(1.0, med + 4.0 * 1.4826 * (mad or 0.0)))
        inliers = [item for item, error in zip(train, errors)
                   if error <= cutoff]
        minimum = max(_MIN_TRAIN, int(math.ceil(len(train) * 0.60)))
        if len(inliers) < minimum:
            return None

        coefficients = None
        for unused in range(2):
            line_x = _least_squares(inliers, x_index, 2)
            line_z = _least_squares(inliers, z_index, 3)
            if line_x is None or line_z is None:
                return None
            coefficients = (line_x, line_z)
            errors = [_residual(item, coefficients, x_index, z_index)
                      for item in train]
            med = _median(errors)
            mad = _median([abs(error - med) for error in errors])
            cutoff = min(cap, max(1.0, med + 4.0 * 1.4826 * (mad or 0.0)))
            next_inliers = [item for item, error in zip(train, errors)
                            if error <= cutoff]
            if len(next_inliers) < minimum:
                return None
            inliers = next_inliers

        # Refit once to the final shared 2D inlier set.
        line_x = _least_squares(inliers, x_index, 2)
        line_z = _least_squares(inliers, z_index, 3)
        if line_x is None or line_z is None:
            return None
        return (line_x, line_z), inliers

    def _fit_model(self, all_points, axis, x_index, z_index):
        train = [item for item in all_points
                 if item["seq"] % _HOLDOUT_MODULUS != 0]
        holdout = [item for item in all_points
                   if item["seq"] % _HOLDOUT_MODULUS == 0]
        self._holdout_count = len(holdout)
        if len(train) < _MIN_TRAIN or len(holdout) < 2:
            return None, "insufficient_holdout", None, None, 0
        train_x_span = _span([item["v"][0] for item in train]) or 0.0
        train_y_span = _span([item["v"][1] for item in train]) or 0.0
        if (train_x_span < _MIN_MAP_SPAN or
                train_y_span < _MIN_MAP_SPAN or
                _covariance_ratio(train) <= _MIN_COVARIANCE_RATIO):
            return None, "insufficient_training_geometry", None, None, 0

        fitted = self._fit_axis_pair(train, x_index, z_index)
        if fitted is None:
            return None, "robust_fit_failed", None, None, 0
        coefficients, inliers = fitted
        if _covariance_ratio(inliers) <= _MIN_COVARIANCE_RATIO:
            return None, "insufficient_training_geometry", None, None, 0
        for line in coefficients:
            if (not _finite(line[0]) or not _finite(line[1]) or
                    abs(line[0]) < _MIN_SCALE or
                    abs(line[0]) > _MAX_SCALE or
                    abs(line[1]) > 1.0e9):
                return None, "unreasonable_coefficients", None, None, 0

        world_x_span = _span([item["v"][2] for item in inliers]) or 0.0
        world_z_span = _span([item["v"][3] for item in inliers]) or 0.0
        if min(world_x_span, world_z_span) < _MIN_WORLD_SPAN:
            return None, "insufficient_world_span", None, None, 0
        residual_limit = max(2.0, max(world_x_span, world_z_span) * 0.015)
        train_rmse = _rmse(inliers, coefficients, x_index, z_index)
        holdout_errors = [_residual(item, coefficients, x_index, z_index)
                          for item in holdout]
        holdout_inliers = [item for item, error in zip(holdout, holdout_errors)
                           if error <= max(residual_limit * 3.0,
                                           max(world_x_span, world_z_span) * 0.05)]
        holdout_outliers = len(holdout) - len(holdout_inliers)
        holdout_rmse = _rmse(holdout_inliers, coefficients, x_index, z_index)
        self._holdout_outliers = holdout_outliers

        # A lone extreme holdout is not trusted at small N. With >=3 clean
        # held-out points, one isolated outlier may be excluded and recorded.
        can_isolate_one = (holdout_outliers == 1 and len(holdout) >= 4 and
                           len(holdout_inliers) >= 3)
        if (train_rmse is None or train_rmse > residual_limit or
                holdout_rmse is None or holdout_rmse > residual_limit or
                (holdout_outliers and not can_isolate_one)):
            return None, "residual_or_holdout_failed", train_rmse, holdout_rmse, holdout_outliers

        model = {
            "axis": axis,
            "x": coefficients[0],
            "z": coefficients[1],
            "x_index": x_index,
            "z_index": z_index,
            "residual_limit": residual_limit,
            "world_scale": max(world_x_span, world_z_span),
        }
        return model, None, train_rmse, holdout_rmse, holdout_outliers

    def _try_fit(self):
        points = list(self._samples)
        if len(points) < _MIN_SAMPLES:
            self._status = "collecting"
            self._reason = "insufficient_samples"
            return

        map_x_span = _span([item["v"][0] for item in points]) or 0.0
        map_y_span = _span([item["v"][1] for item in points]) or 0.0
        if (map_x_span < _MIN_MAP_SPAN or map_y_span < _MIN_MAP_SPAN or
                _covariance_ratio(points) <= _MIN_COVARIANCE_RATIO):
            self._status = "degenerate"
            self._reason = "insufficient_map_span_or_2d_geometry"
            return

        candidates = []
        failure_reasons = []
        for axis, x_index, z_index in (("A", 0, 1), ("B", 1, 0)):
            model, reason, fit_rmse, held_rmse, outliers = self._fit_model(
                points, axis, x_index, z_index)
            if model is not None:
                candidates.append((held_rmse, fit_rmse, model,
                                   held_rmse, outliers))
            else:
                failure_reasons.append(reason)
                if fit_rmse is not None:
                    # Keep useful failure metrics; candidate order is stable.
                    self._rmse = fit_rmse
                    self._holdout_rmse = held_rmse

        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1], item[2]["axis"]))
            unused_score, fit_rmse, model, held_rmse, outliers = candidates[0]
            self._model = model
            self._fit_sample_count = len(points)
            self._status = "available"
            self._reason = None
            self._rmse = fit_rmse
            self._holdout_rmse = held_rmse
            self._holdout_outliers = outliers
            self._holdout_count = sum(
                1 for item in points if item["seq"] % _HOLDOUT_MODULUS == 0)
            return

        if failure_reasons and all(reason == "insufficient_holdout"
                                   for reason in failure_reasons):
            self._status = "collecting"
            self._reason = "insufficient_holdout"
            return
        if (failure_reasons and all(
                reason in ("insufficient_holdout",
                           "insufficient_training_geometry")
                for reason in failure_reasons)):
            self._status = "degenerate"
            self._reason = "insufficient_training_geometry_or_holdout"
            return
        self._status = "rejected"
        self._reason = (failure_reasons[0] if failure_reasons else
                        "no_valid_axis_model")

    def _predicted_error(self, values):
        item = {"v": values}
        return _residual(item, (self._model["x"], self._model["z"]),
                         self._model["x_index"], self._model["z_index"])

    def _reset_fit_and_samples(self):
        self._samples = []
        self._seen = 0
        self._sequence = 0
        self._rng = 1
        self._model = None
        self._status = "collecting"
        self._reason = "calibration_drift"
        self._fit_sample_count = 0
        self._rmse = None
        self._holdout_rmse = None
        self._holdout_count = 0
        self._holdout_outliers = 0
        self._drift_streak = 0

    def observe(self, samples, now):
        """Observe ``(nx, ny, worldX, worldZ)`` pairs at monotonic ``now``.

        Invalid and non-finite values are ignored. A backwards timestamp
        starts a fresh calibration epoch before processing the new batch.
        Returns a diagnostics snapshot for convenient call-site logging.
        """
        timestamp = _number(now)
        if timestamp is None:
            return self.snapshot()
        if self._last_now is not None and timestamp < self._last_now:
            self.clear()
        self._last_now = timestamp
        parsed = self._parse_samples(samples)

        if self._model is not None and parsed:
            errors = [self._predicted_error(values) for values in parsed]
            drift_limit = max(4.0, self._model["world_scale"] * 0.02)
            bad = [error > drift_limit for error in errors]
            if sum(1 for value in bad if value) > len(bad) / 2.0:
                self._drift_streak += 1
                if self._drift_streak >= _DRIFT_BATCHES:
                    self._reset_fit_and_samples()
                    self._append_many(parsed)
                    return self.snapshot()
                # Do not contaminate an established reservoir with suspect data.
                return self.snapshot()
            self._drift_streak = 0
            self._append_many([values for values, is_bad in zip(parsed, bad)
                               if not is_bad])
            return self.snapshot()

        if self._append_many(parsed):
            self._try_fit()
        return self.snapshot()

    def _span_snapshot(self):
        if not self._samples:
            return {"mapX": None, "mapY": None,
                    "worldX": None, "worldZ": None}
        return {
            "mapX": _span([item["v"][0] for item in self._samples]),
            "mapY": _span([item["v"][1] for item in self._samples]),
            "worldX": _span([item["v"][2] for item in self._samples]),
            "worldZ": _span([item["v"][3] for item in self._samples]),
        }

    def snapshot(self):
        """Return a fresh JSON-safe diagnostics dictionary."""
        coefficients = None
        if self._model is not None:
            x_map_name = "nx" if self._model["x_index"] == 0 else "ny"
            z_map_name = "nx" if self._model["z_index"] == 0 else "ny"
            coefficients = {
                "axis": self._model["axis"],
                "worldX": {"mapAxis": x_map_name,
                           "scale": self._model["x"][0],
                           "offset": self._model["x"][1]},
                "worldZ": {"mapAxis": z_map_name,
                           "scale": self._model["z"][0],
                           "offset": self._model["z"][1]},
            }
        return {
            "source": "temporal_map_fit",
            "status": self._status,
            "reason": self._reason,
            "sampleCount": len(self._samples),
            "fitSampleCount": self._fit_sample_count,
            "driftStreak": self._drift_streak,
            "span": self._span_snapshot(),
            "rmse": self._rmse,
            "holdoutRmse": self._holdout_rmse,
            "holdoutCount": self._holdout_count,
            "holdoutOutlierCount": self._holdout_outliers,
            "coefficients": coefficients,
            "coordinateUnit": "game_world",
            "inferred": True,
        }

    def map_to_world(self, mx, my):
        """Convert normalized map ``(mx,my)`` to ``[worldX,0,worldZ]``."""
        if self._model is None:
            return None
        mx = _number(mx)
        my = _number(my)
        if mx is None or my is None or mx < 0.0 or mx > 1.0 or my < 0.0 or my > 1.0:
            return None
        values = (mx, my)
        world_x = (self._model["x"][0] * values[self._model["x_index"]] +
                   self._model["x"][1])
        world_z = (self._model["z"][0] * values[self._model["z_index"]] +
                   self._model["z"][1])
        if not _finite(world_x) or not _finite(world_z):
            return None
        return [world_x, 0, world_z]

    def world_to_map(self, x, z):
        """Convert finite world X/Z to normalized ``[nx,ny]``, or ``None``."""
        if self._model is None:
            return None
        x = _number(x)
        z = _number(z)
        if x is None or z is None:
            return None
        first = (x - self._model["x"][1]) / self._model["x"][0]
        second = (z - self._model["z"][1]) / self._model["z"][0]
        values = [None, None]
        values[self._model["x_index"]] = first
        values[self._model["z_index"]] = second
        if (not _finite(values[0]) or not _finite(values[1]) or
                values[0] < 0.0 or values[0] > 1.0 or
                values[1] < 0.0 or values[1] > 1.0):
            return None
        return values
