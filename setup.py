import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="Proxy Kernel",
    version="0.0.1",
    author="Kyle Kelley",
    author_email="rgbkrk@gmail.com",
    description="A small example package",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rgbkrk/proxy-kernel",
    packages=setuptools.find_packages(),
    entry_points={"console_scripts": ["prok=proxy_kernel:main"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
