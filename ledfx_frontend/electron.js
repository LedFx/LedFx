/* eslint-disable no-console */
/* eslint-disable global-require */
/* eslint-disable @typescript-eslint/no-var-requires */
const path = require('path')
const isDev = require('electron-is-dev')
const { app, nativeTheme, BrowserWindow, ipcMain, shell } = require('electron')
const { isCC } = require('./app/core.js')
const { createWindow } = require('./app/win.js')
const { createTray } = require('./app/tray.js')
const { startInstance, closeAllSubs } = require('./app/instances.js')
const { handlers } = require('./app/handlers.js')
const { installDevtools } = require('./app/devtools.js')
const { setupProtocol, handleProtocol } = require('./app/protocol.js')

require('events').EventEmitter.defaultMaxListeners = 15

let installExtension
if (isDev) {
  const devTools = require('electron-devtools-installer')
  installExtension = devTools.default
}

const subpy = null
const subprocesses = {}
let wind
let win

setupProtocol()
const gotTheLock = app.requestSingleInstanceLock()

const ready = () =>
  app.whenReady().then(async () => {
    nativeTheme.themeSource = 'dark'
    const thePath = process.env.PORTABLE_EXECUTABLE_DIR || path.resolve('.')

    wind = isCC
      ? createWindow(win, { additionalArguments: ['integratedCore'] })
      : createWindow(win)

    require('@electron/remote/main').enable(wind.webContents)

    wind.webContents.setWindowOpenHandler(({ url }) => {
      if (url.includes(' https://accounts.spotify.com/authorize')
      // || url.includes(`${backendUrl}/connect/github?callback`)
      ) {
        shell.openExternal(url)
        // return { action: 'deny' }
      }
      return { action: 'allow' }
    })

    if (isCC) startInstance(wind, 'instance1', subprocesses)
    if (isDev) installDevtools(installExtension)

    createTray(isCC, wind, thePath, __dirname)

    ipcMain.on('toMain', async (event, parameters) =>
      handlers(wind, subprocesses, event, parameters)
    )
    wind.on('close', () => {
      closeAllSubs(wind, subpy, subprocesses)
      wind = null;
    })
  })

handleProtocol(() => wind, gotTheLock, ready)

app.on('window-all-closed', () => {
  closeAllSubs(wind, subpy, subprocesses)
  app.quit()
})

app.on('before-quit', () => closeAllSubs(wind, subpy, subprocesses))

app.on(
  'activate',
  () => BrowserWindow.getAllWindows().length === 0 && createWindow()
)
