/* eslint-disable */

import { IMCell } from '../pages/Devices/EditVirtuals/EditMatrix/M.utils'

/* eslint-disable @typescript-eslint/indent */
export const drawerWidth = 240
export const frontendConfig = 12

export const formatTime = (dura: number) => {
  let seconds: string | number
  let minutes: string | number
  seconds = Math.floor((dura / 1000) % 60)
  minutes = Math.floor((dura / (1000 * 60)) % 60)
  minutes = minutes < 10 ? `0${minutes}` : minutes
  seconds = seconds < 10 ? `0${seconds}` : seconds

  return `${minutes}:${seconds}`
}

export const camelToSnake = (str: string) =>
  str[0].toLowerCase() +
  str
    .slice(1, str.length)
    .replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)

export const download = (
  content: any,
  fileName: string,
  contentType: string
) => {
  const a = document.createElement('a')
  const file = new Blob([JSON.stringify(content, null, 4)], {
    type: contentType
  })
  a.href = URL.createObjectURL(file)
  a.download = fileName
  a.click()
}

export const getOverlapping = (data: any) => {
  const tmp = {} as any
  data.forEach(([name, start, end]: [string, number, number]) => {
    if (!tmp[name]) {
      tmp[name] = {}
      data.forEach(() => {
        tmp[name].items = []
        tmp[name].overlap = false
        tmp[name].items.push([start, end])
      })
    } else {
      tmp[name].items.push([start, end])
    }
  })
  Object.keys(tmp).forEach((e) =>
    tmp[e].items
      .sort(([startA]: [number], [startB]: [number]) => startA > startB)
      .forEach(([start, end]: [number, number], i: number) => {
        if (tmp[e].items[i + 1]) {
          const [startNew, endNew] = tmp[e].items[i + 1]
          if (startNew <= end && endNew >= start) {
            tmp[e].overlap = true
          }
        }
      })
  )
  return tmp
}

export const swap = (array: any[], i: number, j: number) => {
  const arr = [...array]
  arr[i] = arr.splice(j, 1, arr[i])[0]
  return arr
}

export const deleteFrontendConfig = () => {
  window.localStorage.removeItem('undefined')
  window.localStorage.removeItem('ledfx-storage')
  window.localStorage.removeItem('ledfx-host')
  window.localStorage.removeItem('ledfx-hosts')
  window.localStorage.removeItem('ledfx-ws')
  window.localStorage.removeItem('ledfx-theme')
  window.localStorage.removeItem('ledfx-frontend')
  window.location.reload()
}

export const initFrontendConfig = () => {
  if (
    parseInt(window.localStorage.getItem('ledfx-frontend') || '0', 10) >=
    frontendConfig
  ) {
    return
  }
  deleteFrontendConfig()
  window.localStorage.setItem('ledfx-frontend', `${frontendConfig}`)
}

export const log = (...props: any[]) => {
  if (typeof props[0] === 'string') {
    // eslint-disable-next-line no-console
    console.log(
      `%c ${props[0]
        .replace('success', '')
        .replace('warning', '')
        .replace('info', '')} `,
      `padding: 3px 5px; border-radius: 5px; background: #${
        props[0].indexOf('success') !== -1
          ? '1db954; color: #fff; font-weight: 700;'
          : props[0].indexOf('info') !== -1
          ? '0dbedc; color: #fff; font-weight: 700;'
          : props[0].indexOf('warning') !== -1
          ? 'FF7514; color: #fff; font-weight: 700;'
          : '800000; color: #fff;'
      }`,
      ...props.slice(1, props.length)
    )
  }
}

export const sleep = (ms: number) => {
  // eslint-disable-next-line no-promise-executor-return
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export const filterKeys = (obj: Record<string, any>, keys = [] as string[]) => {
  // NOTE: Clone object to avoid mutating original!
  const objct = JSON.parse(JSON.stringify(obj))

  keys.forEach((key) => delete objct[key])

  return objct
}

export const ordered = (unordered: Record<string, any>) =>
  Object.keys(unordered)
    .sort()
    .reduce((obj: any, key) => {
      // eslint-disable-next-line no-param-reassign
      obj[key] = unordered[key]
      return obj
    }, {})

export function transpose(matrix: IMCell[][]) {
  const res = [] as IMCell[][]
  for (let i = 0; i < matrix[0].length; i++) {
    res[i] = [] as IMCell[]
    for (let j = 0; j < matrix.length; j++) {
      res[i][j] = matrix[j][i]
    }
  }
  return res
}

export const ios =
  /iPad|iPhone|iPod/.test(navigator.userAgent) ||
  (navigator.userAgent === 'MacIntel' && navigator.maxTouchPoints > 1)

export const padTo2Digits = (num: any) => {
  return num.toString().padStart(2, '0')
}

export const getTime = (milliseconds: any) => {
  let seconds = Math.floor(milliseconds / 1000)
  let minutes = Math.floor(seconds / 60)
  let hours = Math.floor(minutes / 60)

  seconds %= 60
  minutes %= 60
  hours %= 24

  return `${padTo2Digits(hours)}:${padTo2Digits(minutes)}:${padTo2Digits(
    seconds
  )}`
}

export const logScale = (value: number) => {
  const minp = 0; // Adjusted from 1 to 0
  const maxp = 14; // Log2(16384) = 14
  const minv = Math.log2(50); // Adjusted from 1 to 50
  const maxv = Math.log2(16384);
  const scale = (maxv-minv) / (maxp-minp);
  return Math.pow(2, minv + scale*(value-minp));
}

export const inverseLogScale = (value: number) => {
  const minp = 0; // Adjusted from 1 to 0
  const maxp = 14; // Log2(16384) = 14
  const minv = Math.log2(50); // Adjusted from 1 to 50
  const maxv = Math.log2(16384);
  const scale = (maxv-minv) / (maxp-minp);
  return (Math.log2(value)-minv) / scale + minp;
}

export function deepEqual(obj1: any, obj2: any) {
  if (obj1 === obj2) {
    return true;
  }

  if (typeof obj1 !== 'object' || obj1 === null || typeof obj2 !== 'object' || obj2 === null) {
    return false;
  }

  let keys1 = Object.keys(obj1).sort();
  let keys2 = Object.keys(obj2).sort();

  if (keys1.length !== keys2.length) {
    return false;
  }

  for (let i = 0; i < keys1.length; i++) {
    if (keys1[i] !== keys2[i] || !deepEqual(obj1[keys1[i]], obj2[keys2[i]])) {
      return false;
    }
  }

  return true;
}
