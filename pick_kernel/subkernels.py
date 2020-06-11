from .exceptions import PickRegistrationException

from jupyter_client import AsyncKernelManager

import entrypoints


class Subkernels(object):
    def __init__(self):
        self._subkernels = {}

    def register(self, name, subkernel):
        self._subkernels[name] = subkernel

    def register_entry_points(self):
        """Register entrypoints for a subkernel
        Load handlers provided by other packages
        """
        for entrypoint in entrypoints.get_group_all("pick_kernel.subkernel"):
            self.register(entrypoint.name, entrypoint.load())

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
            if not getattr(self._subkernels[name], "hidden", False)
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
    hidden = True

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


# Instantiate a SubKernels instance, register Handlers and entrypoints
_subkernels = Subkernels()
_subkernels.register(None, DefaultKernel)
_subkernels.register("ipykernel", DefaultKernel)
_subkernels.register_entry_points()

# Expose registration at a top level
register = _subkernels.register
list_subkernels = _subkernels.list_subkernels
get_subkernel = _subkernels.get_subkernel
