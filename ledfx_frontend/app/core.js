const fs = require('fs');
const path = require('path');
const isDev = require('electron-is-dev');
const Store = require('electron-store');
const { app } = require('electron');
const store = new Store();

const coreFile = {
    'darwin': 'LedFx_core.app/Contents/MacOS/LedFx_v2',
    'linux': 'LedFx',
    'win32': 'LedFx/LedFx.exe'
  };

  const defaultCoreParams = {
    'darwin': {
      'instance1': []
    },
    'linux': {
      'instance1': ['-p', '8888', '--no-tray']
    },
    'win32': {
      'instance1': ['-p', '8888', '--no-tray']
    }
  };

const coreParams = store.get('coreParams', defaultCoreParams);

const corePath = (file) => path.join(path.dirname(__dirname), isDev ? '../extraResources' : '../../extraResources', file)
const runCore = (file, options) => require('child_process').spawn(`${corePath(file)}`, options).on('error', (err) => { console.error(`Failed to start subprocess. ${err}`); });

if (!fs.existsSync(path.join(app.getPath("userData"), '.ledfx-cc'))) {
  console.log('Creating .ledfx-cc folder')
  fs.mkdirSync(path.join(app.getPath("userData"), '.ledfx-cc'));
}
function startCore(wind, platform, instance = 'instance1', port = '8889') {
    let subpy;

    if (fs.existsSync(corePath(coreFile[platform]))) {
      if (coreParams[platform] && instance && coreParams[platform][instance]) {
        if (instance !== 'instance1') {

          coreParams[platform][instance] = ['-p', port, '-c', path.join(app.getPath("userData"), '.ledfx-cc', instance)];
        }
        console.log('Starting core with params', platform, instance, coreParams[platform][instance])
        subpy = runCore(coreFile[platform], coreParams[platform][instance]);
      } else {
        coreParams[platform][`instance${Object.keys(coreParams[platform]).length + 1}`] = ['-p', port, '-c', path.join(app.getPath("userData"), '.ledfx-cc', instance)];
        console.log('Creating core with params', platform, Object.keys(coreParams[platform]).length, coreParams[platform][`instance${Object.keys(coreParams[platform]).length}`])
        subpy = runCore(coreFile[platform], coreParams[platform][`instance${Object.keys(coreParams[platform]).length}`]);
      }
      store.set('coreParams', coreParams);
      wind.webContents.send('fromMain', ['coreParams', coreParams[process.platform]]);
      if (subpy !== null) {
        subpy.on('stdout', (data) => {
          console.log(`stdout: ${data}`);
        });
        subpy.stdout.on('data', (data) => {
          console.log(`stdout: ${data}`);
        });
        subpy.stderr.on('data', (data) => {
          console.log(`stderr: ${data}`);
          wind.webContents.send('fromMain', ['snackbar', data.toString()]);
        });
        subpy.on('exit', (code, signal) => {
          console.log(`Child process exited with code ${code} and signal ${signal}`);
        });
        subpy.on('error', (err) => {
          console.error(`Failed to start subprocess. ${err}`);
        });
      }
    }
    return subpy;
  }

const isCC = fs.existsSync(corePath(coreFile[process.platform]))

module.exports = { startCore, corePath, isCC, coreFile, coreParams, store, defaultCoreParams };
