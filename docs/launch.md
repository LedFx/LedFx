# Command Line Options

When launching LedFx from the command line, or by editing properties of a desktop shortcut it is possible to add various launch options explained below.

- `--version`: Display the current version of LedFx.
- `-c, --config <directory>`: Specify the directory that contains the configuration files. Defaults to .ledfx in the user data directory according to host OS
- `--open-ui`: Automatically open the web interface
- `-v, --verbose`: Set log level to INFO.
- `-vv, --very-verbose`: Set log level to DEBUG.
- `-p, --port <port>`: Specify the web interface port (HTTP). Default 8888
- `-p_s, --port_secure <port>`: Specify the web interface port (HTTPS). Default 8443 SSL certs must be present in the ledfx config directory
- `--host <address>`: Specify the address to host the LedFx web interface. Default localhost, 127.0.0.1
- `--tray`: Force LedFx system tray icon.
- `--no-tray`: Force no LedFx system tray icon.
- `--offline`: Disable crash logger and auto update checks.
- `--sentry-crash-test`: Crash LedFx to test the sentry crash logger.
- `--ci-smoke-test`: Launch LedFx and then exit after 5 seconds to sanity check the install.
- `--clear-config`: Launch LedFx, backup the config, clear the config, and continue with a clean startup.
- `--clear-effects`: Launch LedFx, load the config, clear all active effects on all virtuals. Effect configurations are persisted, just turned off.
- `--pause-all`: Start LedFx with all virtuals paused. This is a global pause and can be toggled via the UI, or via a rest PUT to /api/virtuals


## Adding Command-Line Options to LedFx Launch

This guide explains how to add command-line options to the launch of `ledfx` across **Windows**, **Linux**, and **macOS**, including instructions for both creating new shortcuts and editing pre-existing ones.

---

### Windows

#### Adding Options via Command Prompt

1. Open **Command Prompt**.
2. Navigate to the folder where `ledfx` is located using the `cd` command.
3. Run `ledfx` with the desired options appended to the command:

   ```console
   ledfx [options]
   ```

#### Adding Options to a Shortcut

##### Creating a New Shortcut
1. Right-click on your desktop or a folder and select **New > Shortcut**.
2. In the **Type the location of the item** field, provide the full path to the `ledfx.exe` executable, followed by the desired options:

   ```console
   "C:\Path\To\LedFx\ledfx.exe" [options]
   ```

3. Click **Next**, name the shortcut (e.g., `LedFx Custom Launch`), and click **Finish**.
4. Double-click the shortcut to launch `ledfx` with the specified options.

##### Editing an Existing Shortcut
1. Locate the existing shortcut (e.g., on the desktop or in a folder).
2. Right-click the shortcut and select **Properties**.
3. In the **Shortcut** tab, find the **Target** field. Add the desired options to the end of the existing path. For example:

   ```console
   "C:\Path\To\LedFx\ledfx.exe" [options]
   ```

4. Click **OK** to save the changes.
5. Launch `ledfx` using the shortcut with the updated options.

---

### Linux

#### Adding Options via Terminal

1. Open a terminal.
2. If `ledfx` is installed globally, append options to the `ledfx` command:

   ```bash
   ledfx [options]
   ```

   If installed in a virtual environment, activate the virtual environment first, then run:

   ```bash
   source /path/to/venv/bin/activate
   ledfx [options]
   ```

#### Adding Options to a Desktop Launcher

##### Creating a New Launcher
1. Create a `.desktop` file in `~/.local/share/applications/` (e.g., `ledfx-custom.desktop`).
2. Add the following content, replacing `[options]` with the desired options:

   ```ini
   [Desktop Entry]
   Name=LedFx Custom Launch
   Exec=ledfx [options]
   Type=Application
   Terminal=true
   ```

3. Save the file and make it executable:

   ```bash
   chmod +x ~/.local/share/applications/ledfx-custom.desktop
   ```

4. Launch `ledfx` from your desktop environment's application menu with the specified options.

##### Editing an Existing Launcher
1. Locate the existing `.desktop` file, typically in `~/.local/share/applications/`.
2. Open the file with a text editor.
3. Find the `Exec` line and append the desired options to the command. For example:

   ```ini
   Exec=ledfx [options]
   ```

4. Save the file and exit the editor.
5. The launcher will now include the specified options when executed.

---

### macOS

:::: warning
::: title
Warning
:::

This section needs updating by those who understand the ways of Mac OS
::::



#### Adding Options via Terminal

1. Open the **Terminal**.
2. Run the `ledfx` command with options appended:

   ```bash
   ledfx [options]
   ```

   If using a virtual environment, activate it first:

   ```bash
   source /path/to/venv/bin/activate
   ledfx [options]
   ```

#### Adding Options via Automator Application

##### Creating a New Automator Application
1. Open **Automator** and create a new **Application**.
2. Add the **Run Shell Script** action.
3. Enter the `ledfx` command with the desired options:

   ```bash
   /path/to/ledfx [options]
   ```

4. Save the Automator application (e.g., `LedFx Custom Launch`) to your Applications folder.
5. Double-click the Automator application to launch `ledfx` with the specified options.

##### Editing an Existing Automator Application
1. Open the **Automator** application containing your `ledfx` launch workflow.
2. Locate the **Run Shell Script** action and edit the command to include the desired options:

   ```bash
   /path/to/ledfx [options]
   ```

3. Save the changes.
4. The Automator application will now launch `ledfx` with the updated options.
