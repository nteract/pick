import os
import sys

from tornado.ioloop import IOLoop

import zmq
from zmq.eventloop import ioloop

import base64

from binascii import hexlify
import os

from queue import Empty

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


class PickyKernel(Kernel):
    implementation = "picky"
    implementation_version = __version__

    # This banner only shows on `jupyter console` (at the command line).
    banner = """Pick, the kernel for choosy users! ⛏ 

Read more about it at https://github.com/rgbkrk/pick
    """

    # NOTE: This may not match the underlying kernel we launch. However, we need a default
    #       for the initial launch.
    # TODO: Dynamically send over the underlying kernel's kernel_info_reply later
    language_info = {
        "name": "python",
        "version": sys.version.split()[0],
        "mimetype": "text/x-python",
        "codemirror_mode": {"name": "ipython", "version": sys.version_info[0]},
        "pygments_lexer": "ipython3",
        "nbconvert_exporter": "python",
        "file_extension": ".py",
    }

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
        self.kernel_launched = asyncio.Event()

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

        # TODO: pass config into kernel launch
        km = AsyncKernelManager(
            kernel_name="python3",
            # Pass our IPython session as the session for the KernelManager
            session=self.session,
            # Use the same ZeroMQ context that allows for awaiting on recv
            context=self.future_context,
            connection_file=cf,
            # TODO: Figure out if this can be relied on
            # extra_arguments=["-c", "x = 89898977"],
            # extra_env={},
        )

        # Due to how kernel_cmd is no longer in vogue, we have to set
        # this extra field that just plain has to be set
        km.extra_env = {}

        if config is None:
            config = ""

        km.kernel_cmd = [
            "python3",
            "-m",
            "ipykernel_launcher",
            "-f",
            "{connection_file}",
            "-c",
            f"""the_config = '''{config}''';""",
        ]
        self.log.info("launching child kernel with")
        self.log.info(km.kernel_cmd)

        await km.start_kernel()

        kernel = KernelProxy(manager=km, shell_upstream=self.shell_stream)
        self.iosub.connect(kernel.iopub_url)

        # Make sure the kernel is really started. We do that by using
        # kernel_info_requests here.
        #
        # In the future we should incorporate kernel logs (output of the kernel process), then
        # and send back all the information back to the user as display output.

        # Create a temporary KernelClient for waiting for the kernel to start
        kc = km.client()
        kc.start_channels()

        # Wait for kernel info reply on shell channel
        while True:
            self.log.debug("querying kernel info")
            kc.kernel_info(reply=False)
            try:
                msg = await kc.shell_channel.get_msg(timeout=1)
            except Empty:
                pass
            else:
                if msg["msg_type"] == "kernel_info_reply":
                    # Now we know the kernel is (mostly) ready.
                    # However, most kernels are not quite ready at this point to send
                    # on more execution.
                    #
                    # Do we wait for a further status: idle on iopub?
                    # Wait for idle?
                    # Wait for particular logs from the stdout of the kernel process?
                    break

            if not await kc.is_alive():
                # TODO: Emit child kernel death message into the notebook output
                raise RuntimeError("Kernel died before replying to kernel_info")
                self.log.error("Kernel died while launching")

            # Wait before sending another kernel info request
            await asyncio.sleep(0.1)

        # Flush IOPub channel on our (temporary) kernel client
        while True:
            try:
                msg = await kc.iopub_channel.get_msg(timeout=0.2)
            except Empty:
                break

        # Clean up our temporary kernel client
        kc.stop_channels()

        # Inform all waiters for the kernel that it is ready
        self.kernel_launched.set()

        return kernel

    async def get_kernel(self):
        # Ensure that the kernel is launched
        await self.kernel_launched.wait()
        if self.child_kernel is None:
            self.log.error("the child kernel was not available")

        return self.child_kernel

    async def queue_before_relay(self, stream, ident, parent):
        kernel = await self.get_kernel()
        self.session.send(kernel.shell, parent, ident=ident)

    def _publish_display_data(
        self, data, metadata=None, transient=None, parent=None, update=False
    ):
        """publish display data"""
        if metadata is None:
            metadata = {}
        if transient is None:
            transient = {}

        content = {"data": data, "metadata": metadata, "transient": transient}

        self.session.send(
            self.iopub_socket,
            "update_display_data" if update else "display_data",
            content,
            parent=parent,
            ident=self._topic("display_data"),
        )

    async def launch_or_reuse_kernel(self, strema, ident, parent):
        # Ensure that only one coroutine is getting a kernel
        async with self.acquiring_kernel:
            if self.child_kernel is None:
                kernel_display_id = hexlify(os.urandom(8)).decode("ascii")

                self._publish_display_data(
                    {"text/markdown": "Preparing default kernel..."},
                    transient={"display_id": kernel_display_id},
                    parent=parent,
                )

                # NOTE: this is the default kernel launch with no config passed
                self.child_kernel = await self.start_kernel()
                self._publish_display_data(
                    # Wipe out the previous message
                    {"text/markdown": ""},
                    transient={"display_id": kernel_display_id},
                    parent=parent,
                    update=True,
                )
            else:
                # We can just assume to pass the child kernel at this point
                pass

        self.session.send(self.child_kernel.shell, parent, ident=ident)

    async def launch_kernel_with_parameters(self, stream, ident, parent, config):
        content = parent["content"]
        code = content["code"]
        # NOTE: We are, for the time being, ignoring the silent flag, store_history, etc.
        self._publish_execute_input(code, parent, self.execution_count)
        self._publish_status("busy")

        kernel_display_id = hexlify(os.urandom(8)).decode("ascii")

        self._publish_display_data(
            {"text/markdown": "Launching customized runtime..."},
            transient={"display_id": kernel_display_id},
            parent=parent,
        )

        # Ensure that only one coroutine is getting a kernel
        async with self.acquiring_kernel:
            if self.child_kernel is None:
                self.child_kernel = await self.start_kernel(config)
                self._publish_display_data(
                    {"text/markdown": "Runtime ready!"},
                    transient={"display_id": kernel_display_id},
                    parent=parent,
                    update=True,
                )
            else:
                self._publish_display_data(
                    {
                        "text/markdown": """
## Kernel already configured and launched.

You can only run the `%%kernel.config` cell at the top of your notebook and the
start of your session. Please **restart your kernel** and run the cell again if
you want to change configuration.
"""
                    },
                    transient={"display_id": kernel_display_id},
                    parent=parent,
                    update=True,
                )

        # Complete the "execution request" so the jupyter client (e.g. the notebook) thinks
        # execution is finished
        reply_content = {
            "status": "ok",
            # TODO: Adjust this since we're one step behind the "real" kernel
            "execution_count": self.execution_count,
            # Note: user_expressions are not supported on our kernel creation magic
            "user_expressions": {},
            "payload": {},
        }

        metadata = {"parametrized-kernel": True, "status": reply_content["status"]}

        self.session.send(
            stream,
            "execute_reply",
            reply_content,
            parent,
            metadata=metadata,
            ident=ident,
        )
        self._publish_status("idle")

    def parse_cell(self, cell):
        if not cell.startswith("%%kernel."):
            return None

        try:
            # Split off our config from the kernel magic name
            _, raw_config = cell.split("\n", 1)

            return raw_config
        except Exception:
            return None

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
            asyncio.create_task(self.launch_or_reuse_kernel(stream, ident, parent))

    def relay_to_kernel(self, stream, ident, parent):
        # relay_to_kernel is synchronous, and we rely on an asynchronous start
        # so we create each kernel message as a task...
        asyncio.create_task(self.queue_before_relay(stream, ident, parent))

        # TODO: All non-execution requests prior to the kernel starting up must be queued
        #       up otherwise they're starting a kernel currently...

    execute_request = relay_execute_to_kernel
    inspect_request = relay_to_kernel
    complete_request = relay_to_kernel


class PickyKernelApp(IPKernelApp):
    kernel_class = PickyKernel
    # TODO: Uncomment this to disable IO Capture of this kernel
    # outstream_class = None


main = PickyKernelApp.launch_instance
