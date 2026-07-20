from demo_command_center.cli.doctor import diagnostic_report
from demo_command_center.config.settings import Settings


def test_doctor_never_claims_unvalidated_integration() -> None:
    report = diagnostic_report(Settings(_env_file=None))
    assert report["environment"] == "local"
    for status in report["checks"].values():
        assert status["connection_validated"] is False
        assert status["sandbox_validated"] is False
        assert status["live_integration_tested"] is False
