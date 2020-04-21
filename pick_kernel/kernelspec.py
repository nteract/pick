"""The Pick kernel spec for Jupyter"""

import errno
import json
import os
import shutil
import sys
import tempfile

from jupyter_client.kernelspec import KernelSpecManager

pjoin = os.path.join

KERNEL_NAME = "picky-python%i" % sys.version_info[0]

from ipykernel import kernelspec as ipyks

# Yoink resources from the IPython kernel's resources
RESOURCES = pjoin(os.path.dirname(ipyks.__file__), "resources")


def make_pick_kernel_cmd(
    mod="pick_kernel", executable=None, extra_arguments=None, **kw
):
    """Build Popen command list for launching a Picky kernel.

    Parameters
    ----------
    mod : str, optional (default 'pick_kernel')
        A string of a Pick kernel module whose __main__ starts a Pick kernel

    executable : str, optional (default sys.executable)
        The Python executable to use for the kernel process.

    extra_arguments : list, optional
        A list of extra arguments to pass when executing the launch code.
        The most common use for this is to pass --Application.log_level='INFO' in order to
        get logs from the Pick kernel.

    Returns
    -------

    A Popen command list
    """
    if executable is None:
        executable = sys.executable
    extra_arguments = extra_arguments or []
    arguments = [executable, "-m", mod, "-f", "{connection_file}"]
    arguments.extend(extra_arguments)

    return arguments


def get_kernel_dict(extra_arguments=None):
    """Construct dict for kernel.json"""
    return {
        "argv": make_pick_kernel_cmd(extra_arguments=extra_arguments),
        "display_name": "Picky Python %i" % sys.version_info[0],
        "language": "python",
    }


def write_kernel_spec(path=None, overrides=None, extra_arguments=None):
    """Write a kernel spec directory to `path`
    
    If `path` is not specified, a temporary directory is created.
    If `overrides` is given, the kernelspec JSON is updated before writing.
    
    The path to the kernelspec is always returned.
    """
    if path is None:
        path = os.path.join(tempfile.mkdtemp(suffix="_kernels"), KERNEL_NAME)

    # stage resources
    shutil.copytree(RESOURCES, path)
    # write kernel.json
    kernel_dict = get_kernel_dict(extra_arguments)

    if overrides:
        kernel_dict.update(overrides)
    with open(pjoin(path, "kernel.json"), "w") as f:
        json.dump(kernel_dict, f, indent=1)

    return path


def install(
    kernel_spec_manager=None,
    user=False,
    kernel_name=KERNEL_NAME,
    display_name=None,
    prefix=None,
):
    """Install the Picky kernelspec for Jupyter
    
    Parameters
    ----------
    
    kernel_spec_manager: KernelSpecManager [optional]
        A KernelSpecManager to use for installation.
        If none provided, a default instance will be created.
    user: bool [default: False]
        Whether to do a user-only install, or system-wide.
    kernel_name: str, optional
        Specify a name for the kernelspec.
        This is needed for having multiple Picky kernels for different environments.
    display_name: str, optional
        Specify the display name for the kernelspec
    prefix: str, optional
        Specify an install prefix for the kernelspec.
        This is needed to install into a non-default location, such as a conda/virtual-env.

    Returns
    -------
    
    The path where the kernelspec was installed.
    """
    if kernel_spec_manager is None:
        kernel_spec_manager = KernelSpecManager()

    if (kernel_name != KERNEL_NAME) and (display_name is None):
        # kernel_name is specified and display_name is not
        # default display_name to kernel_name
        display_name = kernel_name
    overrides = {}
    if display_name:
        overrides["display_name"] = display_name
    else:
        extra_arguments = None
    path = write_kernel_spec(overrides=overrides, extra_arguments=extra_arguments)
    dest = kernel_spec_manager.install_kernel_spec(
        path, kernel_name=kernel_name, user=user, prefix=prefix
    )
    # cleanup afterward
    shutil.rmtree(path)
    return dest


# Entrypoint

from traitlets.config import Application


class InstallPickyKernelSpecApp(Application):
    """Dummy app wrapping argparse"""

    name = "picky-kernel-install"

    def initialize(self, argv=None):
        if argv is None:
            argv = sys.argv[1:]
        self.argv = argv

    def start(self):
        import argparse

        parser = argparse.ArgumentParser(
            prog=self.name, description="Install the Picky kernel spec."
        )
        parser.add_argument(
            "--user",
            action="store_true",
            help="Install for the current user instead of system-wide",
        )
        parser.add_argument(
            "--name",
            type=str,
            default=KERNEL_NAME,
            help="Specify a name for the kernelspec."
            " This is needed to have multiple Picky kernels at the same time.",
        )
        parser.add_argument(
            "--display-name",
            type=str,
            help="Specify the display name for the kernelspec."
            " This is helpful when you have multiple Picky kernels.",
        )
        parser.add_argument(
            "--prefix",
            type=str,
            help="Specify an install prefix for the kernelspec."
            " This is needed to install into a non-default location, such as a conda/virtual-env.",
        )
        parser.add_argument(
            "--sys-prefix",
            action="store_const",
            const=sys.prefix,
            dest="prefix",
            help="Install to Python's sys.prefix."
            " Shorthand for --prefix='%s'. For use in conda/virtual-envs." % sys.prefix,
        )
        opts = parser.parse_args(self.argv)
        try:
            dest = install(
                user=opts.user,
                kernel_name=opts.name,
                prefix=opts.prefix,
                display_name=opts.display_name,
            )
        except OSError as e:
            if e.errno == errno.EACCES:
                print(e, file=sys.stderr)
                if opts.user:
                    print("Perhaps you want `sudo` or `--user`?", file=sys.stderr)
                self.exit(1)
            raise
        print("Installed kernelspec %s in %s" % (opts.name, dest))


main = InstallPickyKernelSpecApp.launch_instance

if __name__ == "__main__":
    InstallPickyKernelSpecApp.launch_instance()
