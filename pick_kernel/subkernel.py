from .exceptions import PickRegistrationException

from jupyter_client import AsyncKernelManager


class SubKernels(object):
    def __init__(self):
        self._subkernels = {}

    def register(self, name, subkernel):
        self._subkernels[name] = subkernel

    def get_subkernel(self, name=None):
        """Retrieves an engine by name."""
        subkernel = self._subkernels.get(name)
        if not subkernel:
            raise PickRegistrationException(f"No subkernel named {name} found")
        return subkernel

    def list_subkernels(self):
        """Returns a list of available subkernels"""
        return [
            f"%%kernel.{name}"
            for name in filter(lambda x: x is not None, self._subkernels.keys())
        ]

    def launch_subkernel(self, name=None):
        return self.get_subkernel(name).launch()


class Subkernel(object):
    """
    Base class for subkernels.

    Other specific subkernels should inherit and implement the `launch` method.
    """

    @staticmethod
    async def launch(config, session, context, connection_file):
        """This must return an AsyncKernelManager() that has
        already had start_kernel called on it"""
        raise NotImplementedError("launch must be implemented")


class DefaultKernel(Subkernel):
    @staticmethod
    async def launch(config, session, context, connection_file):
        args = []
        if config:
            # configuration passed to the default kernel passes options to ipykernel
            args = list(filter(lambda x: x != "", config.split("\n")))

        km = AsyncKernelManager(
            kernel_name="python3",
            # Pass our IPython session as the session for the KernelManager
            session=session,
            # Use the same ZeroMQ context that allows for awaiting on recv
            context=context,
            connection_file=connection_file,
        )

        # Tack on additional arguments to the underlying kernel
        await km.start_kernel(extra_arguments=args)

        return km


# Instantiate a SubKernels instance, register Handlers
_subkernels = SubKernels()
_subkernels.register(None, DefaultKernel)
_subkernels.register("ipykernel", DefaultKernel)

# Expose registration at a top level
register = _subkernels.register
list_subkernels = _subkernels.list_subkernels
get_subkernel = _subkernels.get_subkernel
