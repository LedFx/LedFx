# Document Development

The documentation is written in markdown. Once you are finished
making changes, you must build the documentation. To build the LedFx
documentation follow the steps outlined below:

We have now migrated document dependancy management and build to uv
based.

Building should be the same for all platforms. These instructions assume you already have a poetry environment setup, as per normal development.

This is most simply built via vscode as per [Docs in VScode](#docs-in-vscode) but instructions are provided below if you work in some other environment.

The docs dependancies are managed in the `pyproject.toml`
file. To install the docs dependancies, run the following command:

``` console
uv sync --group docs
```

To build the documentation, run the following commands

``` console
$ cd docs
$ uv run sphinx-build -a -b html . build
```

The built docs can be checked in the docs/build directory by opening the index.html file.

## Docs in VScode

Tasks have been added to the .vscode file to make building docs smoother and removing any excuse not to improve them ( hint hint ).

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
