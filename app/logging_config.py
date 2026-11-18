import logging
import os


LOG_DIRECTORY = os.path.join(
    os.path.dirname(__file__),
    "logs"
)


def setup_loggers():
    os.makedirs(LOG_DIRECTORY, exist_ok=True)

    access_logger = logging.getLogger("securestay.access")
    auth_logger = logging.getLogger("securestay.auth")
    app_logger = logging.getLogger("securestay.app")

    access_logger.setLevel(logging.INFO)
    auth_logger.setLevel(logging.INFO)
    app_logger.setLevel(logging.INFO)

    access_logger.propagate = False
    auth_logger.propagate = False
    app_logger.propagate = False

    if not access_logger.handlers:
        access_handler = logging.FileHandler(
            os.path.join(LOG_DIRECTORY, "access.log")
        )
        access_handler.setFormatter(
            logging.Formatter("%(message)s")
        )
        access_logger.addHandler(access_handler)

    if not auth_logger.handlers:
        auth_handler = logging.FileHandler(
            os.path.join(LOG_DIRECTORY, "auth.log")
        )
        auth_handler.setFormatter(
            logging.Formatter("%(message)s")
        )
        auth_logger.addHandler(auth_handler)

    if not app_logger.handlers:
        app_handler = logging.FileHandler(
            os.path.join(LOG_DIRECTORY, "app.log")
        )
        app_handler.setFormatter(
            logging.Formatter("%(message)s")
        )
        app_logger.addHandler(app_handler)

    return access_logger, auth_logger, app_logger