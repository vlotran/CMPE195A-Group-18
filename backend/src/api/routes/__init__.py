"""API route modules"""

from . import health
from . import sensors
from . import configurations
from . import alerts
from . import auth
from . import camera
from . import actuators

__all__ = ["health", "sensors", "configurations", "alerts", "auth", "camera", "actuators"]