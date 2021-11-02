const path = require('path');

const { app, Menu, Tray, nativeImage, Notification, nativeTheme, BrowserWindow } = require('electron');
const isDev = require('electron-is-dev');

// Conditionally include the dev tools installer to load React Dev Tools
let installExtension, REACT_DEVELOPER_TOOLS; // NEW!

if (isDev) {
    const devTools = require("electron-devtools-installer");
    installExtension = devTools.default;
    REACT_DEVELOPER_TOOLS = devTools.REACT_DEVELOPER_TOOLS;
}

// Handle creating/removing shortcuts on Windows when installing/uninstalling
if (require("electron-squirrel-startup")) {
    app.quit();
}

let win

function createWindow() {
    require('@electron/remote/main').initialize()
    // Create the browser window.
    win = new BrowserWindow({
        width: 480,
        height: 768,
        autoHideMenuBar: true,
        // frame: false,
        webPreferences: {
            // preload: path.join(__dirname, 'preload.js'),
            enableRemoteModule: true,
            nodeIntegration: true,
            contextIsolation: false,
        }
    });
    // and load the index.html of the app.
    // win.loadFile("index.html");
    win.loadURL(
        isDev
            ? 'http://localhost:3000'
            : `file://${path.join(__dirname, '../build/index.html')}`
    );

    // win.removeMenu()

    // Open the DevTools.
    // if (isDev) {
    //     win.webContents.openDevTools({ mode: 'detach' });
    // }
    return win
}

const NOTIFICATION_TITLE = 'LedFx Client - by Blade'
const NOTIFICATION_BODY = 'Testing Notification from the Main process'

function showNotification() {
    new Notification({ title: NOTIFICATION_TITLE, body: NOTIFICATION_BODY }).show()
}

let tray = null

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.

app.whenReady().then(() => {
    nativeTheme.themeSource = 'dark';
    const wind = createWindow();

    if (isDev) {
        installExtension(REACT_DEVELOPER_TOOLS)
            .then(name => console.log(`Added Extension:  ${name}`))
            .catch(error => console.log(`An error occurred: , ${error}`));
    }

    const icon = path.join(__dirname, 'icon_16x16.png')
    tray = new Tray(icon)
    const contextMenu = Menu.buildFromTemplate([
        { label: 'Show', click: () => wind.show() },
        { label: 'Minimize', click: () => wind.minimize() },
        { label: 'Minimize to tray', click: () => wind.hide() },
        { label: 'Test Notifiation', click: () => showNotification() },
        { label: 'seperator', type: 'separator' },
        { label: 'Dev', click: () => wind.webContents.openDevTools() },
        { label: 'seperator', type: 'separator' },
        { label: 'Exit', click: () => app.quit() }
    ])
    tray.setToolTip('LedFx Client')
    tray.setContextMenu(contextMenu)
});

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});