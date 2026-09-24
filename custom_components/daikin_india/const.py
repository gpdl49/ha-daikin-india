"""Constants for the Daikin India integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "daikin_india"

CONF_CONNECTION: Final = "connection"
CONNECTION_LOCAL: Final = "local"
CONNECTION_CLOUD: Final = "cloud"

CONF_PIN: Final = "pin"
CONF_PHONE: Final = "phone"
CONF_TOKENS: Final = "tokens"
CONF_INSTALL_UUID: Final = "install_uuid"

LOCAL_SCAN_INTERVAL: Final = timedelta(seconds=20)
CLOUD_SCAN_INTERVAL: Final = timedelta(seconds=60)
