import os
import setuptools

local_path = os.path.dirname(__file__)
# Fix for tox which manipulates execution pathing
if not local_path:
    local_path = "."
here = os.path.abspath(local_path)

# Get the long description from the README file
with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()


def read(fname):
    with open(fname, "r") as fhandle:
        return fhandle.read()


def read_reqs(fname):
    req_path = os.path.join(here, fname)
    return [req.strip() for req in read(req_path).splitlines() if req.strip()]


# Borrowing from the pattern used by papermill for requirements
all_reqs = []
dev_reqs = read_reqs("requirements-dev.txt") + all_reqs
extras_require = {
    "test": dev_reqs,
    "dev": dev_reqs,
    "all": all_reqs,
}


setuptools.setup(
    name="pick_kernel",
    version="0.0.1",
    author="Kyle Kelley",
    author_email="rgbkrk@gmail.com",
    description="The Jupyter Kernel for Choosy Users",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rgbkrk/pick",
    packages=setuptools.find_packages(),
    entry_points={
        "console_scripts": [
            "pick=pick_kernel:main",
            "pick-install=pick_kernel.kernelspec:main",
        ]
    },
    python_requires=">=3.6",
    install_requires=read_reqs("requirements.txt"),
    extras_require=extras_require,
    classifiers=[
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
)
