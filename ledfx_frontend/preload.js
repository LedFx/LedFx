/* eslint-disable no-new */
/* eslint-disable @typescript-eslint/no-var-requires */
/* eslint-disable import/no-extraneous-dependencies */
const { contextBridge, ipcRenderer } = require('electron');
// const customTitlebar = require('@treverix/custom-electron-titlebar');
// const customTitlebar = require('custom-electron-titlebar');

contextBridge.exposeInMainWorld('api', {
  send: (channel, data) => {
    // Whitelist channels
    const validChannels = ['toMain'];
    if (validChannels.includes(channel)) {
      ipcRenderer.send(channel, data);
    }
  },
  receive: (channel, func) => {
    const validChannels = ['fromMain'];
    if (validChannels.includes(channel)) {
      // Deliberately strip event as it includes `sender`
      ipcRenderer.on(channel, (event, ...args) => func(...args));
    }
  },
  yz: true,
});

// contextBridge.exposeInMainWorld('electron', {
//   // ...other APIs to expose to renderer process
//   platform: () => ipcRenderer.send(process.platform)
// });

// window.addEventListener('DOMContentLoaded', () => {
//   new customTitlebar.Titlebar({
//     backgroundColor: customTitlebar.Color.fromHex('#202020'),
//     icon: './icon.png',
//     menu: false,
//     titleHorizontalAlignment: 'left',
//   });
// });
