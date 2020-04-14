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

import asyncio


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

    banner = "Wrapped Kernel"

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

        self.acquiring_kernel = asyncio.Lock()

    def start(self):
        super().start()
        loop = IOLoop.current()
        # Collect and send all IOPub messages, for all time
        # TODO: create as an asyncio.Task, register a done callback with error logging
        loop.add_callback(self.relay_iopub_messages)

    async def relay_iopub_messages(self):
        while True:
            # Get message from our
            msg = await self.iosub.recv_multipart()
            # Send the message up to our consumer (e.g. notebook)
            self.iopub_socket.send_multipart(msg)

    async def start_kernel(self):
        # Create a connection file that is named as a child of this kernel
        base, ext = os.path.splitext(self.parent.connection_file)
        cf = "{base}-child{ext}".format(base=base, ext=ext,)

        self.log.debug("start our child kernel")

        # TODO: configurability heads into here
        km = AsyncKernelManager(
            kernel_name="python3",
            # Pass our IPython session as the session for the KernelManager
            session=self.session,
            # TODO: Understand better
            # The ZeroMQ Context is not our own
            context=self.future_context,
            connection_file=cf,
        )

        await km.start_kernel()

        kernel = KernelProxy(manager=km, shell_upstream=self.shell_stream)
        self.iosub.connect(kernel.iopub_url)

        # TODO: Make sure the kernel is really started
        # This is currently pretend. Our next step is repeatedly checking on
        # the kernel with kernel_info_requests as well as looking at kernel logs
        # which we'll be able to use to customize information sent back to the user
        await asyncio.sleep(3)

        return kernel

    async def get_kernel(self):
        # Ensure that only one coroutine is getting a kernel
        async with self.acquiring_kernel:
            if self.kernel is None:
                self.kernel = await self.start_kernel()

        return self.kernel

    def relay_execute_to_kernel(self, stream, ident, parent):
        # Check for configuraiton code first
        content = parent["content"]
        cell = content["code"]

        # Check cell for our config
        # While also checking if this is the first cell run

        content["code"] = cell

        # relay_to_kernel is synchronous, and we rely on an asynchronous start
        # so we create each kernel message as a task...
        asyncio.create_task(self.queue_before_relay(stream, ident, parent))

    async def queue_before_relay(self, stream, ident, parent):
        kernel = await self.get_kernel()

        self.session.send(kernel.shell, parent, ident=ident)

    def relay_to_kernel(self, stream, ident, parent):
        # relay_to_kernel is synchronous, and we rely on an asynchronous start
        # so we create each kernel message as a task...
        asyncio.create_task(self.queue_before_relay(stream, ident, parent))

    execute_request = relay_execute_to_kernel
    inspect_request = relay_to_kernel
    complete_request = relay_to_kernel


class ProxyKernelApp(IPKernelApp):
    kernel_class = ProxiedKernel
    # TODO: Uncomment this to disable IO Capture of this kernel
    # outstream_class = None

    def _log_level_default(self):
        # Turn on debug logs while we hack on this
        return 10


main = ProxyKernelApp.launch_instance
