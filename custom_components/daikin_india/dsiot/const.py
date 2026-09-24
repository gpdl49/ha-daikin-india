"""Constants taken from the Daikin India app (in.co.daikin.remoapp 1.5.2)."""

CLOUD_HOST = "prod.daikinacmanager.com"
ACCOUNT_HOST = "prod-clubdaikin.daikinacmanager.com"

MULTIREQ_PATH = "/dsiot/multireq"
LOCAL_BASE = "/dsiot/edge"

# App-level OAuth client values hardcoded in the app (not per-user secrets).
CLIENT_ID = "7k8koegnvimcqj7i5p933rov73"
CLIENT_SECRET = "1upkumrsbds2513lccgi6sfatqji5sk8m7vrb9cqfrg2i7nigu5o"
APP_CODE = "CI000000"
DEVICE_MODEL = "HomeAssistant"

DISCOVERY_PORT = 30050
DISCOVERY_SOURCE_PORTS = range(30000, 30051)
DISCOVERY_PAYLOAD = b"DAIKIN_UDP/common/basic_info"
