"""archvyrt plain provisioner"""

# stdlib
import logging
# archvyrt
from archvyrt.provisioner.base import Base

LOG = logging.getLogger(__name__)


class PlainProvisioner(Base):
    """
    Plain Provisioner
    """

    def cleanup(self):
        """
        plain provisioner does not need to do any cleanup
        """
        pass
