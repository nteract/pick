import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

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
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
