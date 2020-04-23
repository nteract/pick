![pick](https://user-images.githubusercontent.com/836375/80047181-94e7df80-84c1-11ea-9fea-f2d8f0fc0258.png)

Customize your kernels on launch!

_Not ready for wide installation yet. If you're ready to try it out, start with the development version detailed below._

## Requirements

- Python 3.7

## Development

Clone the repository and install it in dev mode:

```
git clone https://github.com/rgbkrk/pick
cd pick
pip3 install -e .
```

Create the kernelspec

```
pick-install --user
```

## Purpose & Background

We want a way to launch resources in the background that a kernel needs and inform the user when the kernel is ready. A few examples of this are creating a conda environment, launching a spark cluster, or running an ipython kernel inside of a conda environment.

At first, we wanted to take the approach of changing the Jupyter APIs to allow setting additional parameters on launch. This would have required changes at the `/api/kernelspecs`, `/api/kernel`, each of the UIs, and even the way that kernels are launched by the notebook server, jupyter client, jupyter console, and papermill.

Instead, we're taking the approach of using a kernel magic, in the style of other cell magics. As an example, here's a kernel magic for creating a kernel that uses a conda environment:

```
%%kernel.conda-environment

name: example-environment
channels:
  - conda-forge
dependencies:
  - numpy
  - psutil
  - toolz
  - matplotlib
  - dill
  - pandas
  - partd
  - bokeh
  - dask
```

In action, it works like this:

![image](https://user-images.githubusercontent.com/836375/80048778-0164dd80-84c6-11ea-8d6c-a90ec45aefcc.png)

While the underlying kernel is still getting ready, logs are emitted to the frontend and the UI is still responsive.

The same can be done with setting up spark and its associated environment variables in advance of launching the ipython kernel, or other more creative ways of starting a kernel from an environment.

## Truth: It's a kernel proxy!

The design here is intended to make it really easy for a user to configure a kernel without having to mess with extensions across all the myriad jupyter projects. Instead it's a regular kernel that manages a "child" kernel underneath it.

We set up the initial communications protocol with the jupyter client, whether that be the notebook server or papermill, then after the `%%kernel.*` magic is run we launch the "real" kernel.

![image](https://user-images.githubusercontent.com/836375/80049663-5b66a280-84c8-11ea-8b21-b1be6481b053.png)
