const { BrowserWindow } = require('electron');
const path = require('path');
const isDev = require('electron-is-dev');

function createWindow(win, args = {}) {
  require('@electron/remote/main').initialize();
  // Create the browser window.
  win = new BrowserWindow({
    width: 1024,
    height: 1024,
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
      backgroundThrottling: false,
      nodeIntegration: true,
      contextIsolation: true,
      preload: path.join(__dirname, '../preload.js'),
      ...args,
    },
  });

  win.loadURL(
    isDev
      ? 'http://localhost:3000'
      : `file://${path.join(__dirname, '../../build/index.html')}`
  );

  return win;
}

module.exports = { createWindow };