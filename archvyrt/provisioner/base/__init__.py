import logging
import os
import subprocess

LOG = logging.getLogger('archvyrt')


class Base:
    """
    Base provisioner for domain
    """

    def __init__(self, domain):
        """
        Initialize provisioner
        """
        self._domain = domain

    @property
    def domain(self):
        """
        Libvirt domain, this provisioner is attached to
        """
        return self._domain

    @staticmethod
    def _runcmd(cmds, output=False, failhard=True, **kwargs):
        """
        Run a unix command
        """
        # output shall be captured
        if output:
            LOG.debug('Run command: %s', ' '.join(cmds))
            rval = subprocess.check_output(
                cmds,
                stderr=subprocess.STDOUT,
                **kwargs
            ).decode()
        # output does not matter, send it to /dev/null
        else:
            with open(os.devnull, 'w') as devnull:
                LOG.debug('Run command: %s', ' '.join(cmds))
                rval = subprocess.call(
                    cmds,
                    stdout=devnull,
                    stderr=devnull,
                    **kwargs
                )
            if not rval == 0:
                if failhard:
                    raise RuntimeError('Command %s failed, env: %s' % (" ".join(cmds), kwargs.get('env', 'default')))
        return rval

    @staticmethod
    def writefile(filename, lines, mode='w'):
        """
        Write to a file
        """
        LOG.debug('Write file %s', filename)
        with open(filename, mode) as fobj:
            fobj.write('%s\n' % '\n'.join(lines))

    def cleanup(self):
        """
        cleanup actions
        """
        raise NotImplementedError
