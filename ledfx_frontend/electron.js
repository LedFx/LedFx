const path = require('path');

const { app, Menu, Tray, nativeImage, Notification, nativeTheme, BrowserWindow, ipcMain, shell } = require('electron');
const isDev = require('electron-is-dev');
const { download } = require("electron-dl");
const fs = require('fs')

// Conditionally include the dev tools installer to load React Dev Tools
let installExtension, REACT_DEVELOPER_TOOLS, REDUX_DEVTOOLS; // NEW!
if (isDev) {
    const devTools = require("electron-devtools-installer");
    installExtension = devTools.default;
    REACT_DEVELOPER_TOOLS = devTools.REACT_DEVELOPER_TOOLS;
    REDUX_DEVTOOLS = devTools.REDUX_DEVTOOLS;
}

// Handle creating/removing shortcuts on Windows when installing/uninstalling
if (require("electron-squirrel-startup")) {
    app.quit();
}

let win

function createWindow(args) {
    require('@electron/remote/main').initialize()

    // require('@treverix/remote/main').initialize()
    // Create the browser window.
    win = new BrowserWindow({
        width: 480,
        height: 768,
        autoHideMenuBar: true,
        titleBarStyle: "hidden",
        // frame: false,
        webPreferences: {
            webSecurity: false,
            allowRunningInsecureContent: true,
            plugins: true,
            enableRemoteModule: true,
            backgroundThrottling: false,
            nodeIntegration: true,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js'),
            ...args
        }
    });

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
var subpy = null
var contextMenu = null
// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
var wind

app.whenReady().then(async () => {
    nativeTheme.themeSource = 'dark';
    const thePath = process.env.PORTABLE_EXECUTABLE_DIR || path.resolve('.')
    const ledfxCores = fs.readdirSync(thePath).filter(o => (o.length - o.indexOf('--win-portable.exe') === 18) && o.indexOf('LedFx_core') === 0)
    const ledfxCore = ledfxCores && ledfxCores.length && ledfxCores.length > 0 && ledfxCores[ledfxCores.length - 1]
    const integratedCore = ledfxCore && fs.existsSync(`${thePath}/${ledfxCore}`)

    if (integratedCore) {
        subpy = require("child_process").spawn(`./${ledfxCore}`, ["-p", "8888"]);
    }
    wind = (integratedCore) ? createWindow({additionalArguments: ["integratedCore"]}) : createWindow();
    // require('@treverix/remote/main').initialize()
    require("@electron/remote/main").enable(wind.webContents)
    if (isDev) {
        await installExtension([REACT_DEVELOPER_TOOLS, REDUX_DEVTOOLS], { loadExtensionOptions: { allowFileAccess: true }, forceDownload: false })
            .then(name => console.log(`Added Extension:  ${name}`))
            .catch(error => console.log(`An error occurred: , ${error}`));
    }

    const icon = path.join(__dirname, 'icon_16x16a.png')
    tray = new Tray(icon)

    if (integratedCore) {
        contextMenu = Menu.buildFromTemplate([
            { label: 'Show', click: () => wind.show() },
            { label: 'Minimize', click: () => wind.minimize() },
            { label: 'Minimize to tray', click: () => wind.hide() },
            { label: 'Test Notifiation', click: () => showNotification() },
            { label: 'seperator', type: 'separator' },
            { label: 'Dev', click: () => wind.webContents.openDevTools() },
            { label: 'seperator', type: 'separator' },
            { label: 'Start core', click: () => subpy = require("child_process").spawn(`./${ledfxCore}`, []) },
            { label: 'Stop core', click: () => wind.webContents.send('fromMain', 'shutdown') },
            // { label: 'Download core', click: () =>  download(wind, `https://github.com/YeonV/LedFx-Frontend-v2/releases/latest/download/LedFx_core-${app.getVersion().split('-')[1]}--win-portable.exe`, { directory: thePath, overwrite: true }).then((f) => { app.relaunch(); app.exit() }) },
            { label: 'Restart Client', click: () => { app.relaunch(); app.exit() }},
            { label: 'Open folder', click: () => shell.openPath(thePath) },
            { label: 'seperator', type: 'separator' },
            { label: 'Exit', click: () => app.quit() }
        ])
    } else {
        contextMenu = Menu.buildFromTemplate([
            { label: 'Show', click: () => wind.show() },
            { label: 'Minimize', click: () => wind.minimize() },
            { label: 'Minimize to tray', click: () => wind.hide() },
            { label: 'Test Notifiation', click: () => showNotification() },
            { label: 'seperator', type: 'separator' },
            { label: 'Dev', click: () => wind.webContents.openDevTools() },
            { label: 'seperator', type: 'separator' },
            { label: 'Stop core', click: () => wind.webContents.send('fromMain', 'shutdown') },
            // { label: 'Download core', click: () => download(wind, `https://github.com/YeonV/LedFx-Frontend-v2/releases/latest/download/LedFx_core-${app.getVersion().split('-')[1]}--win-portable.exe`, { directory: thePath, overwrite: true, onProgress: (obj)=>{wind.webContents.send('fromMain', ['download-progress', obj])} }).then((f) => { wind.webContents.send('fromMain', 'clear-frontend'); app.relaunch(); app.exit() })},
            { label: 'Restart Client', click: () => {app.relaunch(); app.exit() }},
            { label: 'Open folder', click: () => shell.openPath(thePath) },
            { label: 'seperator', type: 'separator' },
            { label: 'Exit', click: () => app.quit() }
        ])
    }
    tray.setToolTip(`LedFx Client${isDev ? ' DEV' : ''}`)
    tray.setContextMenu(contextMenu)
    tray.setIgnoreDoubleClickEvents(true)
    tray.on('click', (e) => wind.show())

    ipcMain.on("toMain", (event, parameters) => {
        console.log(parameters)
        if (parameters === 'start-core') {
            console.log("Starting Core", ledfxCore)
            if (integratedCore) {
                subpy = require("child_process").spawn(`./${ledfxCore}`, [])
            }
            return
        }
        if (parameters === 'open-config') {
            console.log("Open Config")
            shell.showItemInFolder(path.join(app.getPath('appData'), '/.ledfx/config.json'))
            return
        }
        if (parameters === 'restart-client') {
            app.relaunch(); 
            app.exit();
            return
        }
        if (parameters === 'download-core') {
            download(wind, `https://github.com/YeonV/LedFx-Frontend-v2/releases/latest/download/LedFx_core-${app.getVersion().split('-')[1]}--win-portable.exe`, { directory: thePath, overwrite: true, onProgress: (obj)=>{wind.webContents.send('fromMain', ['download-progress', obj])} }).then((f) => { wind.webContents.send('fromMain', 'clear-frontend'); app.relaunch(); app.exit() })
            return
        }
    });

    if (integratedCore) {
        wind.on('close', ()=>{
            wind.webContents.send('fromMain', 'shutdown')
        })
    }
});

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {        
        if (subpy !== null) {
            subpy.kill("SIGINT");
        }
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});