from demo_command_center.cli.doctor import diagnostic_report


def test_doctor_never_claims_unvalidated_integration() -> None:
    report = diagnostic_report()
    assert report["environment"] == "local"
    for status in report["checks"].values():
        assert status["connection_validated"] is False
        assert status["sandbox_validated"] is False
        assert status["live_integration_tested"] is False
