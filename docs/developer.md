# Development Setup

## Backend Development {#backend-dev}

:::: warning
::: title
Warning
:::

Always be aware of piping commands to any shell - this is the
recommended method for poetry but there are [other
options](https://python-poetry.org/docs/#installation).
::::

### Windows

:::: note
::: title
Note
:::

Do not install python from the Windows Store - it will not work with
these instructions.
::::

1.  Install [python](https://www.python.org/downloads/windows/) version
    3.9 or above.

2.  Install [git](https://gitforwindows.org/).

3.  Install [Build Tools for Visual Studio
    2022](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022)

    > -   When asked for Workloads, select \"Desktop development with
    >     C++\"
    >
    > -   
    >
    >     Included
    >
    >     :   -   C++ Build Tools core features
    >         -   C++ 2022 Redistributable Update
    >         -   C++ Core desktop features
    >
    > -   
    >
    >     Optional
    >
    >     :   -   MSVC v143 - VS 2022 C++ x64/x86 build tools (vXX,XX)
    >         -   Windows SDK
    >         -   C++ CMake tools for Windows
    >         -   Testing tools core features - Build Tools
    >         -   C++ AddressSanitizer
    >
    > -   The default install options are appropriate.

4.  Reboot

5.  Install poetry using PowerShell:

    ``` console
    $ (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
    ```

6.  Clone the main branch from the LedFx Github repository:

    ``` console
    $ git clone https://github.com/LedFx/LedFx.git
    ```

7.  Install LedFx and its requirements using poetry:

    ``` console
    $ cd LedFx
    $ poetry install
    ```

8.  This will let you run LedFx directly from the cloned repository via:

    ``` console
    $ poetry run ledfx --open-ui
    ```

### Linux {#linux-dev}

:::: note
::: title
Note
:::

This assumes an apt based system such as ubuntu. If your system uses
another package manager you should be able use it to get the required
packages.
::::

1.  Install poetry:

    ``` console
    $ curl -sSL https://install.python-poetry.org | python3 -
    ```

2.  Clone the main branch from the LedFx Github repository:

    ``` console
    $ git clone https://github.com/LedFx/LedFx.git
    ```

3.  Install system dependencies via `apt install`:

    ``` console
    $ sudo apt install libatlas3-base \
          libavformat58 \
          portaudio19-dev \
          pulseaudio \
          cmake \
    ```

4.  Install LedFx and its requirements using poetry:

    ``` console
    $ cd LedFx
    $ poetry install
    ```

5.  This will let you run LedFx directly from your local copy via:

    ``` console
    $ poetry run ledfx --open-ui
    ```

### macOS {#macos-dev}

1.  Install poetry:

    ``` console
    $ curl -sSL https://install.python-poetry.org | python3 -
    ```

2.  Clone the main branch from the LedFx Github repository:

    ``` console
    $ git clone https://github.com/LedFx/LedFx.git
    ```

3.  Install LedFx and its requirements using poetry:

    ``` console
    $ cd LedFx
    $ poetry install
    ```

4.  This will let you run LedFx directly from your local copy via:

    ``` console
    $ poetry run ledfx --open-ui
    ```

------------------------------------------------------------------------

## Frontend Development

Building the LedFx frontend is different from how the core backend is
built. The frontend is based on React.js and thus uses pnpm as the core
package management.

:::: note
::: title
Note
:::

The following instructions assume you have already followed the steps
above to
`install the LedFx dev environment <backend-dev>`{.interpreted-text
role="ref"} and have the backend running. If you have not done so,
please do so before continuing.
::::

:::: note
::: title
Note
:::

LedFx will need to be running in development mode for everything to
work. To enable development mode, open the `config.json` file in the
`.ledfx` folder and set `dev_mode: true`)
::::

### Windows {#windows-frontend}

**1.** Install Node.js and pnpm:

First, you need to install Node.js. You can download it from [Node.js
official website](https://nodejs.org/en/download/). After installing
Node.js, you can install pnpm via npm (which is installed with Node.js).

``` console
$ npm install -g pnpm
```

**2.** Navigate to the frontend directory and install the dependencies:

``` console
$ cd frontend
$ pnpm install
```

**3.** Start LedFx in developer mode and start the pnpm watcher:

``` console
$ poetry shell ledfx
$ pnpm start
```

At this point, any changes you make to the frontend will be recompiled,
and after a browser refresh, LedFx will pick up the new files. After
development and testing, you will need to run a full build to generate
the appropriate distribution files prior to submitting any changes.

**4.** When you are finished with your changes, build the frontend:

``` console
$ pnpm build
```

### Linux {#linux-frontend}

**1.** Install Node.js:

Node.js is a prerequisite for pnpm. You can install it using your
distribution\'s package manager. For Ubuntu, you can use the following
commands:

``` console
$ sudo apt-get update
$ sudo apt-get install nodejs
```

**2.** Install pnpm:

``` console
$ curl -fsSL https://get.pnpm.io/install.sh | sh -
```

**3.** Navigate to the frontend directory and install the dependencies:

``` console
$ cd frontend
$ pnpm install
```

The easiest way to test and validate your changes is to run a watcher
that will automatically rebuild as you save and then just leave LedFx
running in a separate command window.

**4.** Start LedFx in development mode and start the watcher:

``` console
$ poetry shell ledfx
$ pnpm start
```

At that point any change you make to the frontend will be recompiled and
after a browser refresh LedFx will pick up the new files. After
development and testing you will need to run a full build to generate
the appropriate distribution files prior to submitting any changes.

**5.** When you are finished with your changes, build the frontend:

``` console
$ pnpm build
```

### macOS {#macos-frontend}

**1.** Install nodejs and NPM requirements using
[homebrew](https://docs.brew.sh/Installation):

``` console
$ brew install nodejs
$ brew install pnpm
$ cd ~/frontend
$ pnpm install
```

**2.** Start LedFx in developer mode and start the NPM watcher:

``` console
$ poetry shell ledfx
$ pnpm start
```

**3.** When you are finished with your changes, build the frontend:

``` console
$ pnpm build
```

------------------------------------------------------------------------

## Document Development

The documentation is written in reStructuredText. Once you are finished
making changes, you must build the documentation. To build the LedFx
documentation follow the steps outlined below:

We have now migrated document dependancy management and build to poetry
based.

Building should be the same for all platforms. These instructions assume
you already have a poetry environment setup, as per normal development.

The docs dependancies are managed in the [pyproject.toml]{.title-ref}
file. To install the docs dependancies, run the following command:

``` console
$ poetry install --only docs
```

To build the documentation, run the following commands

``` console
$ poetry shell
$ cd docs
$ ./make html
```

### Docs in vscode

Tasks have been added to the .vscode file to make building docs smoother
and removing any excuse not to improve them ( hint hint ).

Although there are seperate tasks defined in .vscode/tasks.json for
dependancy install, build and open in browser, they are configured such
that it should be just a case of launching the task **Build and Open
Docs**

This should ensure dependancies are in place, build the docs and open
the index.html in your default browser.

Error detection in the build process to prevent the browser open is not
yet implemented. This is a future enhancement.

Find vscode tasks through ctrl+shift+p and type \"Tasks: Run Task\" and
select the task **Build and Open Docs**

Or better, install the Tasks extension by actboy168 into vscode and run
the task from the bottom control bar. All tasks except \"Build and Open
Docs\" are hidden to reduce clutter.

## How it works

Well enough for discussional purposes. This diagram specifically
illustrates audio reactive effects, temporal are similar but have their
own thread loop independant of audio framing.

![Do you want to buy a bridge?](/_static/main_loop.png)

## Useful Tools

### VSCode extensions

For backend development, vscode is the IDE of choice.

There are many extensions that are of use to developers, including but
not limited to

-   Github Copilot
-   Github Pull Requests
-   autoDocsting
-   GitLens
-   Prettier
-   Pylance
-   Python
-   Python Debugger
-   Python Poetry
-   Tasks
-   Teleplot

### Tasks

A simple extension to run tasks from the vscode taskbar at the bottom of
the window.

[Tasks by
actboy168](https://marketplace.visualstudio.com/items?itemName=actboy168.tasks)

Currently only the Build and Open Docs task is exposed. This task will
install dependancies, build the docs and open in your browser, all with
a single click!

![Build and Open Docs, do it!](/_static/howto/taskbar.png)

### Teleplot

Teleplot is a great tool for visualizing data in real time, that can be
the graphing equivalent of print()

It is used during development to quickly graph, and then thrown away, do
not submit teleplot code to the main branch.

General documentation along with rich examples is at [Teleplot
Github](https://github.com/nesnes/teleplot)

A helper Class has been added to the LedFx codebase to make it easier to
use, and is available at ledfx/utils.py

simply import the class and use it as follows

``` python
from ledfx.utils import Teleplot

Teleplot.send(f"my_var_name:{my_var_value}")
```

![A simple graph from audio volume](/_static/howto/teleplot.png)
