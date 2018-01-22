"""archvyrt plain provisioner"""

# stdlib
import logging
# archvyrt
from .base import Provisioner

LOG = logging.getLogger(__name__)


class PlainProvisioner(Provisioner):
    """
    Plain Provisioner
    """

    def cleanup(self):
        """
        plain provisioner does not need to do any cleanup
        """
        pass
