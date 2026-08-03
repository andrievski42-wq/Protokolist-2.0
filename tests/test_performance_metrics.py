from performance_metrics import RecognitionMetrics, format_metrics


def test_faster_than_realtime() -> None:
    metrics = RecognitionMetrics(
        model_name="turbo",
        audio_seconds=20.0,
        processing_seconds=5.0,
        realtime_factor=0.25,
        characters=300,
    )

    assert metrics.faster_than_realtime is True


def test_format_metrics() -> None:
    metrics = RecognitionMetrics(
        model_name="medium",
        audio_seconds=60.0,
        processing_seconds=30.0,
        realtime_factor=0.5,
        characters=1200,
    )

    result = format_metrics(metrics)

    assert "модель=medium" in result
    assert "RTF=0.50" in result
    assert "символов=1200" in result
    assert "быстрее реального времени" in result
