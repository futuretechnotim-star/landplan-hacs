DOMAIN = "landplan"

CONF_TOKEN = "token"
CONF_PLAN_ID = "plan_id"

PLATFORMS: list[str] = ["calendar", "device_tracker", "image", "sensor"]

# LandPlan tag values used to discover physical device map objects
TAG_CAMERA_NODE = "camera-node"
TAG_MESH_NODE = "mesh-node"
TAG_ROBOT = "robot"
DEVICE_TAGS = frozenset({TAG_CAMERA_NODE, TAG_MESH_NODE, TAG_ROBOT})

# Slow coordinator poll interval (seconds)
SLOW_UPDATE_INTERVAL = 300
