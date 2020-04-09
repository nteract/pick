import os
import sys

from tornado.ioloop import IOLoop

import zmq
from zmq.eventloop import ioloop

# ...
ioloop.install()
from zmq.eventloop.future import Context

from jupyter_client import AsyncKernelManager
from ipykernel.kernelbase import Kernel
from ipykernel.kernelapp import IPKernelApp

from .proxy import KernelProxy


banner = """\
Proxies to another kernel, launched underneath
"""

__version__ = "0.1"


# TODO: Investigate a re-write...
class KernelProxy(object):
    """A proxy for a single kernel

    Hooks up relay of messages on the shell channel.
    """

    def __init__(self, manager, shell_upstream):
        self.manager = manager
        # TODO: Connect Control & STDIN
        self.shell = self.manager.connect_shell()
        # The shell channel from the wrapper kernel
        self.shell_upstream = shell_upstream

        # provide the url
        self.iopub_url = self.manager._make_url("iopub")
        IOLoop.current().add_callback(self.relay_shell)

    async def relay_shell(self):
        """Coroutine for relaying any shell replies"""
        while True:
            msg = await self.shell.recv_multipart()
            self.shell_upstream.send_multipart(msg)


class ProxiedKernel(Kernel):
    implementation = "ProxiedKernel"
    implementation_version = __version__
    # TODO: dynamically send over the underlying kernel's kernel_info_reply later...
    language_info = {"name": "python", "mimetype": ""}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO: Unsure, investigate
        self.future_context = ctx = Context()

        # Our subscription to messages from the kernel we launch
        self.iosub = ctx.socket(zmq.SUB)
        self.iosub.subscribe = b""

        # From kernelapp.py, shell_streams is typically shell_stream, control_stream
        self.shell_stream = self.shell_streams[0]

        # We don't have a kernel yet
        self.kernel = None

    def start(self):
        super().start()
        loop = IOLoop.current()
        # Collect and send all IOPub messages, for all time
        # TODO: create as an asyncio.Task, register a done callback with error logging
        loop.add_callback(self.relay_iopub_messages)

    async def relay_iopub_message(self):
        while True:
            # Get message from our
            msg = await self.iosub.recv_multipart()
            # Send the message up to our consumer (e.g. notebook)
            self.iopub_socket.send_multipart(msg)

    async def start_kernel(self):
        # Create a connection file that is named as a child of this kernel
        base, ext = os.path.splitext(self.parent.connection_file)
        cf = "{base}-child{ext}".format(base=base, ext=ext,)

        # TODO: configurability coming here
        km = AsyncKernelManager(
            kernel_name="python3",
            # Pass our IPython session as the session for the KernelManager
            session=self.session,
            # TODO: Understand better
            # The ZeroMQ Context is not our own
            context=self.future_context,
            connection_file=cf,
        )

        # Really start it
        # TODO: Make sure we're not already starting a kernel...
        await km.start_kernel()

        kernel = KernelProxy(manager=km, shell_upstream=self.shell_stream)
        self.iosub.connect(kernel.iopub_url)

        return kernel

    async def get_kernel(self):
        # TODO: Use a asyncio lock to ensure that only one has access to starting a kernel
        if self.kernel is None:
            self.kernel = await self.start_kernel
        return self.kernel

    def relay_execute_to_kernel(self, stream, ident, parent):
        # TODO: Leaving as boilerplate for now....
        # content = parent["content"]
        # cell = content["code"]
        kernel = self.get_kernel()
        self.session.send(kernel.shell, parent, ident=ident)

    def relay_to_kernel(self, stream, ident, parent):
        kernel = self.get_kernel()
        self.session.send(kernel.shell, parent, ident=ident)

    execute_request = relay_execute_to_kernel
    inspect_request = relay_to_kernel
    complete_request = relay_to_kernel


class ProxyKernelApp(IPKernelApp):
    kernel_class = ProxiedKernel
    # TODO: Should we disable IO Capture?
    outstream_class = None


main = ProxyKernelApp.launch_instance
