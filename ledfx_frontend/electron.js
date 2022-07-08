/* eslint-disable @typescript-eslint/indent */
/* eslint-disable import/no-extraneous-dependencies */
/* eslint-disable no-return-assign */
/* eslint-disable no-console */
/* eslint-disable global-require */
/* eslint-disable @typescript-eslint/no-var-requires */
const path = require('path');

const {
  app,
  Menu,
  Tray,
  //   Notification,
  nativeTheme,
  BrowserWindow,
  ipcMain,
  shell,
} = require('electron');
const isDev = require('electron-is-dev');
const { download } = require('electron-dl');
const fs = require('fs');

// Conditionally include the dev tools installer to load React Dev Tools
let installExtension;
let REACT_DEVELOPER_TOOLS;
let REDUX_DEVTOOLS; // NEW!
if (isDev) {
  const devTools = require('electron-devtools-installer');
  installExtension = devTools.default;
  REACT_DEVELOPER_TOOLS = devTools.REACT_DEVELOPER_TOOLS;
  REDUX_DEVTOOLS = devTools.REDUX_DEVTOOLS;
}

// Handle creating/removing shortcuts on Windows when installing/uninstalling
if (require('electron-squirrel-startup')) {
  app.quit();
}

let win;

function createWindow(args = {}) {
  require('@electron/remote/main').initialize();
  // Create the browser window.
  win = new BrowserWindow({
    width: 480,
    height: 768,
    autoHideMenuBar: true,
    titleBarStyle: process.platform === 'darwin' ? 'default' : 'hidden',
    titleBarOverlay:
      process.platform === 'darwin'
        ? false
        : { color: '#333', symbolColor: '#ffffff' },
    frame: process.platform === 'darwin',
    webPreferences: {
      webSecurity: false,
      allowRunningInsecureContent: true,
      plugins: true,
      // enableRemoteModule: true,
      backgroundThrottling: false,
      nodeIntegration: true,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      ...args,
    },
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

  return win;
}

// const NOTIFICATION_TITLE = 'LedFx Client - by Blade';
// const NOTIFICATION_BODY = 'Testing Notification from the Main process';

// function showNotification() {
//   new Notification({
//     title: NOTIFICATION_TITLE,
//     body: NOTIFICATION_BODY,
//   }).show();
// }

let tray = null;
let subpy = null;
let contextMenu = null;
let wind;
let willQuitApp = false

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.

app.whenReady().then(async () => {
  nativeTheme.themeSource = 'dark';
  const thePath = process.env.PORTABLE_EXECUTABLE_DIR || path.resolve('.');

  const integratedCore = (process.platform === 'darwin') 
    ? fs.existsSync(path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx_core.app'))
    : fs.existsSync(path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx-notray.exe'))

  const currentDir = fs.readdirSync(thePath)
  console.log(currentDir)

  if (integratedCore) {
    if (process.platform === 'darwin') {
      subpy = require('child_process').spawn(`${path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx_core.app/Contents/MacOS/LedFx_v2')}`, []);  
    } else {
      subpy = require('child_process').spawn(`${path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx-notray.exe')}`, ['-p', '8888']);
    }
  } 

  wind = integratedCore
    ? createWindow({ additionalArguments: ['integratedCore'] })
    : createWindow();  

  require('@electron/remote/main').enable(wind.webContents);
  
  if (isDev) {
    await installExtension([REACT_DEVELOPER_TOOLS, REDUX_DEVTOOLS], {
      loadExtensionOptions: { allowFileAccess: true },
      forceDownload: false,
    })
      .then((name) => console.log(`Added Extension:  ${name}`))
      .catch((error) => console.log(`An error occurred: , ${error}`));
  }

  const icon = path.join(__dirname, 'icon_16x16a.png');
  tray = new Tray(icon);

  if (integratedCore) {
    contextMenu = Menu.buildFromTemplate([
      { label: 'Show', click: () => {
        if (process.platform === 'darwin') app.dock.show()
        wind.show() 
      }},
      { label: 'Minimize', click: () => wind.minimize() },
      { label: 'Minimize to tray', click: () => {
        if (process.platform === 'darwin') app.dock.hide()
        wind.hide() 
      }},
      //   { label: 'Test Notifiation', click: () => showNotification() },
      { label: 'seperator', type: 'separator' },
      { label: 'Dev', click: () => wind.webContents.openDevTools() },
      { label: 'seperator', type: 'separator' },
      {
        label: 'Start core',
        click: () => (process.platform === 'darwin') 
          ? subpy = require('child_process').spawn(`${path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx_core.app/Contents/MacOS/LedFx_v2')}`, [])
          : subpy = require('child_process').spawn(`${path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx-notray.exe')}`, ['-p', '8888'])
      },
      {
        label: 'Stop core',
        click: () => wind.webContents.send('fromMain', 'shutdown'),
      },
      // { label: 'Download core', click: () =>  download(wind, `https://github.com/YeonV/LedFx-Frontend-v2/releases/latest/download/LedFx_core-${app.getVersion().split('-')[1]}--win-portable.exe`, { directory: thePath, overwrite: true }).then((f) => { app.relaunch(); app.exit() }) },
      {
        label: 'Restart Client',
        click: () => {
          app.relaunch();
          app.exit();
        },
      },
      { label: 'Open folder', click: () => shell.openPath(thePath) },
      { label: 'seperator', type: 'separator' },
      { label: 'Exit', click: () => app.quit() },
    ]);
  } else {
    contextMenu = Menu.buildFromTemplate([
      { label: 'Show', click: () => {
        if (process.platform === 'darwin') app.dock.show()
        wind.show() 
      }},
      { label: 'Minimize', click: () => wind.minimize() },
      { label: 'Minimize to tray', click: () => {
        if (process.platform === 'darwin') app.dock.hide()
        wind.hide() 
      }},
      //   { label: 'Test Notifiation', click: () => showNotification() },
      { label: 'seperator', type: 'separator' },
      { label: 'Dev', click: () => wind.webContents.openDevTools() },
      { label: 'seperator', type: 'separator' },
      {
        label: 'Stop core',
        click: () => wind.webContents.send('fromMain', 'shutdown'),
      },
      // { label: 'Download core', click: () => download(wind, `https://github.com/YeonV/LedFx-Frontend-v2/releases/latest/download/LedFx_core-${app.getVersion().split('-')[1]}--win-portable.exe`, { directory: thePath, overwrite: true, onProgress: (obj)=>{wind.webContents.send('fromMain', ['download-progress', obj])} }).then((f) => { wind.webContents.send('fromMain', 'clear-frontend'); app.relaunch(); app.exit() })},
      {
        label: 'Restart Client',
        click: () => {
          app.relaunch();
          app.exit();
        },
      },
      { label: 'Open folder', click: () => shell.openPath(thePath) },
      { label: 'seperator', type: 'separator' },
      { label: 'Exit', click: () => app.quit() },
    ]);
  }
  tray.setToolTip(`LedFx Client${isDev ? ' DEV' : ''}`);
  tray.setContextMenu(contextMenu);
  tray.setIgnoreDoubleClickEvents(true);
  tray.on('click', () => wind.show());  

  ipcMain.on('toMain', (event, parameters) => {
    console.log(parameters);
    if (parameters === 'get-platform') {
      wind.webContents.send('fromMain', ['platform', process.platform]);
      return;
    }
    if (parameters === 'start-core') {      
      if (integratedCore) {
        if (process.platform === 'darwin') {
          wind.webContents.send('fromMain', ['currentdir', integratedCore, fs.existsSync(path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx_core.app'))]);
          subpy = require('child_process').spawn(`${path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx_core.app/Contents/MacOS/LedFx_v2')}`, []);  
        } else {
          wind.webContents.send('fromMain', ['currentdir', integratedCore, fs.existsSync(path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx-notray.exe'))]);
          subpy = require('child_process').spawn(`${path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx-notray.exe')}`, []);
        }
      }
      return;
    }
    if (parameters === 'open-config') {
      console.log('Open Config');
      wind.webContents.send('fromMain', ['currentdir', path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources')]);
      shell.showItemInFolder(
        path.join(app.getPath('appData'), '/.ledfx/config.json')
      );
      return;
    }
    if (parameters === 'restart-client') {
      app.relaunch();
      app.exit();
      return;
    }
    if (parameters === 'download-core') {
      download(
        wind,
        `https://github.com/YeonV/LedFx-Frontend-v2/releases/latest/download/LedFx_core-${
          app.getVersion().split('-')[1]
        }--win-portable.exe`,
        {
          directory: thePath,
          overwrite: true,
          onProgress: (obj) => {
            wind.webContents.send('fromMain', ['download-progress', obj]);
          },
        }
      ).then(() => {
        wind.webContents.send('fromMain', 'clear-frontend');
        app.relaunch();
        app.exit();
      });
    }
  });  

  wind.on('close', function(e){
    if (subpy !== null) {
      subpy.kill('SIGINT');
    }
  })
});

app.on('window-all-closed', () => {
    app.quit();
});

app.on('before-quit', () => {
  if (subpy !== null) {
    subpy.kill('SIGINT');
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
