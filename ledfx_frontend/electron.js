/* eslint-disable @typescript-eslint/indent */
/* eslint-disable import/no-extraneous-dependencies */
/* eslint-disable no-return-assign */
/* eslint-disable no-console */
/* eslint-disable global-require */
/* eslint-disable @typescript-eslint/no-var-requires */
const path = require('path');
const Store = require('electron-store');
const store = new Store();

const {
  app,
  Menu,
  Tray,
  // Notification,
  nativeTheme,
  BrowserWindow,
  ipcMain,
  shell,
  session
} = require('electron');
const isDev = require('electron-is-dev');
// const { download } = require('electron-dl');
const fs = require('fs');
const crypto = require('crypto');
const base32Encode = require('base32-encode');
const qrcode = require('qrcode');

require('events').EventEmitter.defaultMaxListeners = 15;

// Conditionally include the dev tools installer to load React Dev Tools
let installExtension;
if (isDev) {
  const devTools = require('electron-devtools-installer');
  installExtension = devTools.default;
}

// Handle creating/removing shortcuts on Windows when installing/uninstalling
if (require('electron-squirrel-startup')) {
  app.quit();
}

const base32Decode = require('base32-decode')

function generateHOTP(secret, counter) {
  const decodedSecret = base32Decode(secret, 'RFC4648');

  const buffer = Buffer.alloc(8);
  for (let i = 0; i < 8; i++) {
    buffer[7 - i] = counter & 0xff;
    counter = counter >> 8;
  }

  // Step 1: Generate an HMAC-SHA-1 value
  const hmac = crypto.createHmac('sha1', Buffer.from(decodedSecret));
  hmac.update(buffer);
  const hmacResult = hmac.digest();

  // Step 2: Generate a 4-byte string (Dynamic Truncation)
  const offset = hmacResult[hmacResult.length - 1] & 0xf;
  const code =
    ((hmacResult[offset] & 0x7f) << 24) |
    ((hmacResult[offset + 1] & 0xff) << 16) |
    ((hmacResult[offset + 2] & 0xff) << 8) |
    (hmacResult[offset + 3] & 0xff);

  // Step 3: Compute an HOTP value
  return `${code % 10 ** 6}`.padStart(6, '0');
}

function generateTOTP(secret, window = 0) {
  const counter = Math.floor(Date.now() / 30000);
  return generateHOTP(secret, counter + window);
}

function verifyTOTP(token, secret, window = 1) {
  for (let errorWindow = -window; errorWindow <= +window; errorWindow++) {
    const totp = generateTOTP(secret, errorWindow);
    if (token === totp) {
      return true;
    }
  }
  return false;
}

let win;

function createWindow(args = {}) {
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

// // function showNotification(title = NOTIFICATION_TITLE, body = NOTIFICATION_BODY) {
// function showNotification(title = NOTIFICATION_TITLE, body = NOTIFICATION_BODY) {
//   new Notification({
//     toastXml: `<toast>
//        <visual>
//          <binding template="ToastText02">
//            <text id="1">LedFx Update available</text>
//            <text id="2">Click the button to see more informations.</text>
//          </binding>
//        </visual>
//        <actions>
//          <action content="Goto Release" activationType="protocol" arguments="https://github.com/YeonV/LedFx-Builds/releases/latest" />
//        </actions>
//     </toast>`,
//  }).show();
// }

let tray = null;
let subpy = null;
let contextMenu = null;
let wind;
let willQuitApp = false

if (process.defaultApp) {
  if (process.argv.length >= 2) {
    app.setAsDefaultProtocolClient('ledfx', process.execPath, [path.resolve(process.argv[1])])
  }
} else {
  app.setAsDefaultProtocolClient('ledfx')
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.


const gotTheLock = app.requestSingleInstanceLock()

const ready = () => (
  app.whenReady().then(async () => {
    nativeTheme.themeSource = 'dark';
    const thePath = process.env.PORTABLE_EXECUTABLE_DIR || path.resolve('.');

    const integratedCore = (process.platform === 'darwin')
      ? fs.existsSync(path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx_core.app'))
      : (process.platform === 'linux') 
        ? fs.existsSync(path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx'))
        : fs.existsSync(path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx/LedFx.exe'))

    const currentDir = fs.readdirSync(thePath)
    console.log(currentDir)

    if (integratedCore) {
      if (process.platform === 'darwin') {
        subpy = require('child_process').spawn(`${path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx_core.app/Contents/MacOS/LedFx_v2')}`, []);
      } else if (process.platform === 'linux') {
        subpy = require('child_process').spawn(`${path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx')}`, ['-p', '8888', '--no-tray']);
      } else {
        subpy = require('child_process').spawn(`${path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx/LedFx.exe')}`, ['-p', '8888', '--no-tray']);
      }
    }

    wind = integratedCore
      ? createWindow({ additionalArguments: ['integratedCore'] })
      : createWindow();

    require('@electron/remote/main').enable(wind.webContents);

    if (isDev) {     
      await installExtension(['lmhkpmbekcpmknklioeibfkpmmfibljd', 'fmkadmapgofadopljbjfkapdkoienihi'], {
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
          click: () => (process.platform === 'darwin')
            ? subpy = require('child_process').spawn(`${path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx_core.app/Contents/MacOS/LedFx_v2')}`, [])
            : (process.platform === 'linux') 
              ? subpy = require('child_process').spawn(`${path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx')}`, ['-p', '8888', '--no-tray'])
              : subpy = require('child_process').spawn(`${path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx/LedFx.exe')}`, ['-p', '8888', '--no-tray'])
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
    tray.setToolTip(`LedFx Client${isDev ? ' DEV' : ''}`);
    tray.setContextMenu(contextMenu);
    tray.setIgnoreDoubleClickEvents(true);
    tray.on('click', () => wind.show());

    wind.webContents.setWindowOpenHandler(({ url }) => {
      if (url.includes(' https://accounts.spotify.com/authorize')) {
        shell.openExternal(url)
      }
      return { action: 'allow' }
    })

    ipcMain.on('toMain', async (event, parameters) => {
      console.log('ALL PARAMS', parameters);
      if (parameters.command === 'verify_otp') {
        const user = store.get('user') || {
          username: 'FreeUser',
          mfaEnabled: false,
          mfaSecret: null
        }
        const token = parameters.token;
        const secret = user.mfaSecret;
        console.log('verify_otp:', user)
        const verified = verifyTOTP(token, secret);
        if (verified) {
          user.mfaEnabled = true;
          store.set('user', user);
        }
        
        console.log('verified_otp:', verified ,user)
        wind.webContents.send('fromMain', ['mfa-verified', verified]);
        return;
      }
      if (parameters.command === 'generate-mfa-qr') {
        const user = store.get('user') || {
          username: 'FreeUser',
          mfaEnabled: false,
          mfaSecret: null
        };
        console.log('generate-mfa-qr:', user)
        // For security, we no longer show the QR code after is verified
        if (user.mfaEnabled) return;
    
        if (!user.mfaSecret) {
          // generate unique secret for user
          // this secret will be used to check the verification code sent by user
          const buffer = crypto.randomBytes(14);
          user.mfaSecret = base32Encode(buffer, 'RFC4648', { padding: false });
          console.log('generated-mfa-qr', user);
          store.set('user', user);
        }
        const issuer = 'Blade\'s LedFx';
        const algorithm = 'SHA1';
        const digits = '6';
        const period = '30';
        const otpType = 'totp';
        const configUri = `otpauth://${otpType}/${issuer}:${user.username}?algorithm=${algorithm}&digits=${digits}&period=${period}&issuer=${issuer}&secret=${user.mfaSecret}`;
    
        qrcode.toDataURL(configUri, {
          color: { dark: '#333333FF', light: '#00000000' },
        }).then((png=>wind.webContents.send('fromMain', ['mfa-qr-code', png])));
    
        return;
      }
      if (parameters === 'get-platform') {
        wind.webContents.send('fromMain', ['platform', process.platform]);
        return;
      }
      if (parameters === 'start-core') {
        if (integratedCore) {
          if (process.platform === 'darwin') {
            wind.webContents.send('fromMain', ['currentdir', integratedCore, fs.existsSync(path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx_core.app'))]);
            subpy = require('child_process').spawn(`${path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx_core.app/Contents/MacOS/LedFx_v2')}`, []);
          } else if (process.platform === 'linux') {
            wind.webContents.send('fromMain', ['currentdir', integratedCore, fs.existsSync(path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx/LedFx'))]);
            subpy = require('child_process').spawn(`${path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx/LedFx')}`, ['-p', '8888', '--no-tray']);
          } else {
            wind.webContents.send('fromMain', ['currentdir', integratedCore, fs.existsSync(path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx/LedFx.exe'))]);
            subpy = require('child_process').spawn(`${path.join(path.dirname(__dirname), isDev ? 'extraResources' : '../extraResources','LedFx/LedFx.exe')}`, []);
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
    });

    wind.on('close', function(e){
      if (subpy !== null) {
        subpy.kill('SIGINT');
        wind.webContents.send('fromMain', 'shutdown');
      }
    })
  })
)

if (process.platform === 'win32') {
  if (!gotTheLock) {
    app.quit()
  } else {
    app.on('second-instance', (event, commandLine, workingDirectory) => {
      // Someone tried to run a second instance, we should focus our window.
      if (wind) {
        if (wind.isMinimized()) wind.restore()
        wind.focus()
        wind.webContents.send('fromMain', ['protocol', JSON.stringify({event, commandLine, workingDirectory})]);
      }
    })
    ready()
    // Handle the protocol. In this case, we choose to show an Error Box.
    app.on('open-url', (event, url) => {
      // event.preventDefault()
      console.log(event, url)
    })

  }
} else {
  ready()
  // Handle the protocol. In this case, we choose to show an Error Box.
  app.on('open-url', (event, url) => {
    // event.preventDefault()
    console.log(event, url)
  })
}



app.on('window-all-closed', () => {
  if (subpy !== null) {
    subpy.kill('SIGINT');
  }
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
