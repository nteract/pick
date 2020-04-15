import os
import sys

from tornado.ioloop import IOLoop

import zmq
from zmq.eventloop import ioloop


from binascii import hexlify
import os

ioloop.install()
# Rely on Socket subclass that returns Futures for recv*
from zmq.eventloop.future import Context

from jupyter_client import AsyncKernelManager
from jupyter_client.session import extract_header
from ipykernel.kernelbase import Kernel
from ipykernel.kernelapp import IPKernelApp

from ipykernel.jsonutil import json_clean

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
        # Ensure the kernel we work with uses Futures on recv, so we can await them
        self.future_context = ctx = Context()

        # Our subscription to messages from the kernel we launch
        self.iosub = ctx.socket(zmq.SUB)
        self.iosub.subscribe = b""

        # From kernelapp.py, shell_streams is typically shell_stream, control_stream
        self.shell_stream = self.shell_streams[0]

        # Start with no child kernel
        self.child_kernel = None

        self.kernel_config = None

        self.acquiring_kernel = asyncio.Lock()

    def start(self):
        super().start()
        loop = IOLoop.current()
        # Collect and send all IOPub messages, for all time
        # TODO: Check errors from this loop and restart as needed (or shut down the kernel)
        loop.add_callback(self.relay_iopub_messages)

    async def relay_iopub_messages(self):
        while True:
            # Get message from our
            msg = await self.iosub.recv_multipart()
            # Send the message up to our consumer (e.g. notebook)
            self.iopub_socket.send_multipart(msg)

    async def start_kernel(self, config=None):
        # Create a connection file that is named as a child of this kernel
        base, ext = os.path.splitext(self.parent.connection_file)
        cf = "{base}-child{ext}".format(base=base, ext=ext,)

        self.log.debug("start our child kernel")

        # TODO: pass config into kernel launch
        km = AsyncKernelManager(
            kernel_name="python3",
            # Pass our IPython session as the session for the KernelManager
            session=self.session,
            # Use the same ZeroMQ context that allows for awaiting on recv
            context=self.future_context,
            connection_file=cf,
        )

        await km.start_kernel()

        kernel = KernelProxy(manager=km, shell_upstream=self.shell_stream)
        self.iosub.connect(kernel.iopub_url)

        # TODO: Make sure the kernel is really started
        #       We can do that using kernel_info_requests as well as looking
        #       at the kernel logs. We can use both of those to customize
        #       the information we send back to the user.
        #
        # For now, we'll pretend the kernel takes 3 seconds to start
        await asyncio.sleep(3)

        return kernel

    async def get_kernel(self):
        # Ensure that only one coroutine is getting a kernel
        async with self.acquiring_kernel:
            if self.child_kernel is None:
                self.child_kernel = await self.start_kernel()

        return self.child_kernel

    async def queue_before_relay(self, stream, ident, parent):
        kernel = await self.get_kernel()
        self.session.send(kernel.shell, parent, ident=ident)

    async def publish_display_data(
        self,
        stream,
        ident,
        parent,
        data,
        metadata=None,
        source=None,
        transient=None,
        update=False,
    ):
        parent_header = extract_header(parent)
        topic = "display_data"

        if metadata is None:
            metadata = {}
        if transient is None:
            transient = {}

        # self._validate_data(data, metadata)
        content = {}
        # TODO TODO TODO define
        # content["data"] = encode_images(data)
        content["data"] = data
        content["metadata"] = metadata
        content["transient"] = transient

        msg_type = "update_display_data" if update else "display_data"

        # Use 2-stage process to send a message,
        # in order to put it through the transform
        # hooks before potentially sending.
        msg = self.session.msg(msg_type, json_clean(content), parent=parent_header)

        # Each transform either returns a new
        # message or None. If None is returned,
        # the message has been 'used' and we return.
        # for hook in self._hooks:
        #     msg = hook(msg)
        #     if msg is None:
        #         return

        self.session.send(
            self.iopub_socket, msg, ident=topic,
        )

    def _publish_display_data(
        self, data, metadata=None, transient=None, parent=None, update=False
    ):
        """send status (busy/idle) on IOPub"""
        if metadata is None:
            metadata = {}
        if transient is None:
            transient = {}

        content = {u"data": data, u"metadata": metadata, u"transient": transient}

        self.session.send(
            self.iopub_socket,
            u"update_display_data" if update else u"display_data",
            content,
            parent=parent,
            ident=self._topic("display_data"),
        )

    async def launch_kernel_with_parameters(self, stream, ident, parent, config):

        content = parent[u"content"]
        code = content[u"code"]
        # TODO: Determine if we care about the silent flag, store_history, etc.
        self._publish_execute_input(code, parent, self.execution_count)
        self._publish_status(u"busy")

        kernel_display_id = hexlify(os.urandom(8)).decode("ascii")

        self.log.debug("launching", kernel_display_id)

        self._publish_display_data(
            {u"text/markdown": u"Launching customized runtime..."},
            transient={u"display_id": kernel_display_id},
            parent=parent,
        )

        # Ensure that only one coroutine is getting a kernel
        # Functionally similar to get_kernel except it passes config
        # and errors when the kernel is already launched
        async with self.acquiring_kernel:
            if self.child_kernel is None:
                self.child_kernel = await self.start_kernel(config)
                self._publish_display_data(
                    {u"text/markdown": u"Runtime ready!"},
                    transient={u"display_id": kernel_display_id},
                    parent=parent,
                    update=True,
                )
            else:
                self._publish_display_data(
                    {
                        u"text/markdown": u"""
## Kernel already configured and launched.

You can only run the `%%kernel.config` cell at the top of your notebook.
Please **restart your kernel** and run the cell again if you want to change
configuration.
"""
                    },
                    transient={u"display_id": kernel_display_id},
                    parent=parent,
                    update=True,
                )

        # Complete the "execution request" so the jupyter client (e.g. the notebook) thinks
        # execution is finished
        reply_content = {
            u"status": u"ok",
            # TODO: Adjust this since we're one step behind the "real" kernel
            u"execution_count": self.execution_count,
            # Note: user_expressions are not supported on our kernel creation magic
            u"user_expressions": {},
            u"payload": {},
        }

        metadata = {u"parametrized-kernel": True, u"status": reply_content["status"]}

        self.session.send(
            stream,
            u"execute_reply",
            reply_content,
            parent,
            metadata=metadata,
            ident=ident,
        )
        self._publish_status(u"idle")

    def parse_cell(self, cell):
        if not cell.startswith("%%kernel.config"):
            return None

        # Strip off the config
        _, raw_config = cell.split("\n", 1)

        # parse the config
        # TODO: incorporate a yaml parser
        return raw_config

    def relay_execute_to_kernel(self, stream, ident, parent):
        # Check for configuraiton code first
        content = parent["content"]
        cell = content["code"]

        # Check cell for our config
        config = self.parse_cell(content["code"])
        if config:
            # Launch the kernel with the config to start
            # However, if the kernel is already started and we see this cell
            # We need to inform the user
            asyncio.create_task(
                self.launch_kernel_with_parameters(stream, ident, parent, config)
            )
            # NOTE: We respond to the execution message in the above task
            return

        else:
            # Run the code or assume we start the default kernel
            # relay_to_kernel is synchronous and we rely on an asynchronous start
            # so we create each kernel message as a task...
            asyncio.create_task(self.queue_before_relay(stream, ident, parent))

    def relay_to_kernel(self, stream, ident, parent):
        # relay_to_kernel is synchronous, and we rely on an asynchronous start
        # so we create each kernel message as a task...
        asyncio.create_task(self.queue_before_relay(stream, ident, parent))

        # TODO: All non-execution requests prior to the kernel starting up must be queued
        #       up otherwise they're starting a kernel currently...

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
