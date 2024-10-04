const path = require('path');
const { app, Menu, shell, Tray } = require('electron');
const { startCore } = require('./core');
const isDev = require('electron-is-dev');
// const { download } = require('electron-dl')

function createMenu(isCC, wind, thePath) {
  let contextMenu;

  if (isCC) {
    contextMenu = Menu.buildFromTemplate([
      { label: 'Show', click: () => {
        if (process.platform === 'darwin') app.dock.show()
        wind.show()        }},
      { label: 'Minimize', click: () => wind.minimize() },
      { label: 'Minimize to tray', click: () => {
        if (process.platform === 'darwin') app.dock.hide()
        wind.hide()
      }},
      // { label: 'Test Notifiation', click: () => showNotification('Update Available', 'v2.0.62') },
      { label: 'seperator', type: 'separator' },
      { label: 'Dev', click: () => wind.webContents.openDevTools() },
      { label: 'seperator', type: 'separator' },
      {
        label: 'Start core',
        click: () => startCore(wind, process.platform, parameters.instance)
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
      // { label: 'Test Notifiation', click: () => showNotification('Update Available', 'v2.0.62') },
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

  return contextMenu;
}


function createTray(isCC, wind, thePath, dir) {
  const icon = path.join(dir, 'icon_16x16a.png');
  let tray = new Tray(icon);

  let contextMenu = createMenu(isCC, wind, thePath);

  tray.setToolTip(`LedFx Client${isDev ? ' DEV' : ''}`);
  tray.setContextMenu(contextMenu);
  tray.setIgnoreDoubleClickEvents(true);
  tray.on('click', () => wind.show());

  return tray;
}

module.exports = { createTray };

