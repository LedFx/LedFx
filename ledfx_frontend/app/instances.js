const { startCore, coreParams } = require('./core')

const poll = async (wind, subprocesses, name, p) => {
  console.log('Polling core', name, 'on port', p)
  if (!p) return
  try {
    const response = await fetch(`http://127.0.0.1:${p}/api/info`)
    const data = await response.json()
    sendStatus(wind, subprocesses, true, name)
    console.log('Polling core succeeded')
  } catch (err) {
    console.log('Polling core ...')
    setTimeout(() => poll(wind, subprocesses, name, p), 1000)
  }
}

function stopInstance(wind, name, subprocesses) {
  if (subprocesses[name]) {
    subprocesses[name].running = false
    sendStatus(wind, subprocesses, false, name)
    subprocesses[name].kill()
  }
}

function startInstance(wind, name, subprocesses, port) {
  try {
    let subpy = startCore(wind, process.platform, name, port)
    if (subpy !== null) {
      subprocesses[name] = subpy
      subprocesses[name].running = true
      sendStatus(wind, subprocesses, false, name)
      poll(wind, subprocesses, name, port)
      subpy.on('exit', () => {
        if (subprocesses[name]) {
          subprocesses[name].running = false
        }
        if (wind && wind.webContents && !wind.isDestroyed() && subprocesses) {
          // `subprocesses` is defined, proceed with calling `sendStatus`
          try {
            sendStatus(wind, subprocesses, false, name);
          } catch (error) {
            console.error(error);
          }
        } else {
          // `subprocesses` is not defined, handle this case as needed
          console.error('subprocesses is not defined');
        }
      })
      subpy.on('error', () => {
        if (subprocesses[name]) {
          subprocesses[name].running = false
        }
        sendStatus(wind, subprocesses, false, name)
      })
    }
  } catch (error) {
    console.error(`Error starting instance "${name}": ${error}`)
  }
}

function sendStatus(wind, subprocesses, connected = false, n) {
  let status = {}
  let platformParams = coreParams[process.platform]
  // Check if `wind` is an instance of `BrowserWindow`
  if (!(wind instanceof require('electron').BrowserWindow)) {
    console.error('wind is not an instance of BrowserWindow');
    return;
  }

  // Check if `subprocesses` is defined
  if (!subprocesses) {
    console.error('subprocesses is not defined');
    return;
  }

  // Check if `n` is defined
  if (!n) {
    console.error('n is not defined');
    return;
  }

  for (let name in platformParams) {
    if (subprocesses && subprocesses[name]) {
      if (name === n) {
        status[name] = connected
          ? 'running'
          : subprocesses[name].running
            ? 'starting'
            : 'stopped'
      } else {
        status[name] = subprocesses[name].running ? 'running' : 'stopped'
      }
    } else {
      status[name] = 'stopped'
    }
  }
  if (wind && wind.webContents  && !wind.isDestroyed() && status) wind.webContents.send('fromMain', ['status', status])
}

function kills(subprocess) {
  if (subprocess !== null) {
    subprocess.kill('SIGINT')
  }
}

function closeAllSubs(wind, subpy, subprocesses) {
  if (wind && wind.webContents && !wind.isDestroyed()) wind.webContents.send('fromMain', 'shutdown')
  if (subpy !== null) kills(subpy)
  if (subprocesses && Object.keys(subprocesses).length > 0) {
    Object.values(subprocesses).forEach((sub) => {
      if (sub) kills(sub)
    })
  }
}

module.exports = {
  poll,
  stopInstance,
  startInstance,
  sendStatus,
  kills,
  closeAllSubs
}
