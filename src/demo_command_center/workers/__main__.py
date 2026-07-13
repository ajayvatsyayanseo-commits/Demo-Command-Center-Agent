from demo_command_center.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    if settings.provider_profile != "real":
        raise SystemExit("Worker requires PROVIDER_PROFILE=real and configured durable adapters.")
    raise SystemExit("Durable SQS worker adapter is not implemented in this architecture phase.")


if __name__ == "__main__":
    main()
