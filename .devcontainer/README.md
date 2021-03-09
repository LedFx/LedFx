# Developing with Visual Studio Code + devcontainer

The easiest way to get started is to use Visual Studio Code with devcontainers. This approach will create a preconfigured development environment with all the tools you need including realtime development.

## Prerequisites

- [git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
- Docker
  -  For Linux, macOS, or Windows 10 Pro/Enterprise/Education use the [current release version of Docker](https://docs.docker.com/install/)
  -   Windows 10 Home requires [WSL 2](https://docs.microsoft.com/windows/wsl/wsl2-install) and the current Edge version of Docker Desktop (see instructions [here](https://docs.docker.com/docker-for-windows/wsl-tech-preview/)). This can also be used for Windows Pro/Enterprise/Education.
- [Visual Studio code](https://code.visualstudio.com/)
- [Remote - Containers (VSC Extension)][extension-link]

[More info about requirements and devcontainer in general](https://code.visualstudio.com/docs/remote/containers#_getting-started)

[extension-link]: https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers

## Getting started:

1. (Fork&) Clone the repository to your computer.
2. Open the repository using Visual Studio code.
3. Run Tasks

When you open this repository with Visual Studio code you are asked to "Reopen in Container", this will start the build of the container.

### Notes
- _If you don't see this notification, open the command palette and select `Remote-Containers: Reopen Folder in Container`._
- _First start will take some time. From the 2nd start on its gonna be fast_

## Tasks

The devcontainer comes with some useful tasks to help you with development, you can start these tasks by opening the command palette and select `Tasks: Run Task` then select the task you want to run.

When a task is currently running, it can be restarted by opening the command palette and selecting `Tasks: Restart Running Task`, then select the task you want to restart.

The available tasks are:

Task | Description
-- | --
Run LedFx in devmode on port 8888 | Backend
Run Ledfx Frontend in devmode on port 3000 | Frontend

