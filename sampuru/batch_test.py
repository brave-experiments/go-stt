import pytest

from sampuru.batch import BatchParameters


def test_update_current_size():
    params = BatchParameters(
        max_latency_ms=1000,
        max_observations=50,
        max_size=10,
        min_size=1,
        update_interval_s=10,
    )
    params.update_current_size(
        previous_batch_sizes=[1, 2, 3],
        previous_batch_times_ms=[100, 150, 200],
        # 50*(i+1) = 50*6 = 300ms per batch for batch size 6
        # 5 * 1000ms / 300ms = 16.6 per second
        jobs_per_second=16,
    )
    assert params.current_size == 5
    assert params.predicted_time_ms == 300


def test_get_timeout():
    params = BatchParameters(max_latency_ms=1000, predicted_time_ms=500)
    assert params.get_timeout() == 500

    params.predicted_time_ms = 1500
    assert params.get_timeout() == 0.01


def test_regress_observations():
    batch_sizes = [1, 2, 3]
    batch_times_ms = [10, 20, 30]
    slope, intercept = BatchParameters.regress_observations(batch_sizes, batch_times_ms)
    assert slope == pytest.approx(10.0)
    assert intercept == pytest.approx(0.0)


def test_predict():
    slope = 10.0
    intercept = 0.0
    assert BatchParameters.predict(slope, intercept, 5) == 50.0


def test_should_update():
    params = BatchParameters(
        current_size=5, predicted_time_ms=100, update_interval_s=10
    )
    assert params.should_update(jobs_per_second=10, batches_processed=17)
    assert not params.should_update(jobs_per_second=10, batches_processed=8)
