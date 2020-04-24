![pick](https://user-images.githubusercontent.com/836375/80047181-94e7df80-84c1-11ea-9fea-f2d8f0fc0258.png)

Customize your kernels on launch!

**Pick**'s magic lets you customize your virtual environments, conda environments, and Jupyter kernels. If you have mountains of data or models, you can use Pick to easily climb to peak efficiency -- composable, on-the-fly environments and kernels created within a notebook cell.

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

When working in a notebook, we want a way to choose resources to launch in the background, create a kernel environment, and inform the user when the kernel and custom resources are ready. Creating a conda environment, launching a spark cluster, or running an ipython kernel inside of a conda environment are examples of things we wanted to do from within a notebook.

When we were looking at initial design, we considered the approach of changing the Jupyter APIs to allow setting additional parameters on launch. This would have required changes at the `/api/kernelspecs`, `/api/kernel`, each of the UIs, and even the way that kernels are launched by the notebook server, jupyter client, jupyter console, and papermill. Possible, but we wanted something simpler for notebook users and developers.

Instead, we decided to use magic -- kernel magic. In the style of other cell magics, we wanted Pick to give users a flexible kernel magic in a notebook cell.

As an example, here's how a kernel magic for creating a kernel that uses a conda environment would work:

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

While Pick is working to get the magic's underlying kernel ready, Pick emits logs to the frontend and keeps the notebook UI responsive.

A similar example with Pick and kernel magics includes setting up spark and its associated environment variables in advance of launching the ipython kernel. Pick opens up possibilities for other creative ways of starting a kernel from an environment.

## Truth: It's a kernel proxy!

Pick's design focuses on making it really easy for a user to configure a kernel without having to mess with extensions across all the myriad jupyter projects or executing tasks from the command line. Pick works as a regular Jupyter kernel with the additional ability to create, customize, and manage a "child" kernel.

We set up Pick's initial communications protocol with the jupyter client, whether that be the notebook server or papermill. Next, the `%%kernel.*` magic runs, and we launch the "real" kernel.

![image](https://user-images.githubusercontent.com/836375/80049663-5b66a280-84c8-11ea-8b21-b1be6481b053.png)
