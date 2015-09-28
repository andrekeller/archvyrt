import logging

from archvyrt.provisioner import Base

LOG = logging.getLogger('archvyrt')


class PlainProvisioner(Base):
    """
    Plain Provisioner
    """

    def cleanup(self):
        """
        plain provisioner does not need to do any cleanup
        """
        pass
