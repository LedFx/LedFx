/* eslint-disable no-param-reassign */
import axios from 'axios'
import { produce } from 'immer'
import isElectron from 'is-electron'
// import { useStore } from '@/store/useStore';
// eslint-disable-next-line import/no-cycle
import useStore from '../store/useStore'
import type { IStore } from '../store/useStore'
// eslint-disable-next-line prettier/prettier
const baseURL = isElectron() ? 'http://localhost:8888' : window.location.href.split('/#')[0].replace(/\/+$/, '') || 'http://localhost:8888';
const storedURL = window.localStorage.getItem('ledfx-host')

const api = axios.create({
  baseURL: storedURL || baseURL
})

// eslint-disable-next-line import/prefer-default-export
export const Ledfx = async (
  path: string,
  method?: 'GET' | 'PUT' | 'POST' | 'DELETE',
  body?: any,
  snackbar: boolean = true
): Promise<any> => {
  const { setState } = useStore
  try {
    let response = null as any
    switch (method) {
      case 'PUT':
        response = await api.put(path, body)
        break
      case 'DELETE':
        response = await api.delete(path, body)
        break
      case 'POST':
        response = await api.post(path, body)
        break

      default:
        response = await api.get(path)
        break
    }
    if (response.data && response.data.payload && snackbar) {
      setState(
        produce((state: IStore) => {
          state.ui.snackbar = {
            isOpen: true,
            messageType: response.data.payload.type || 'error',
            message:
              response.data.payload.reason ||
              response.data.payload.message ||
              JSON.stringify(response.data.payload)
          }
        })
      )
      if (response.data.status) {
        return response.data
      }
    }
    if (response.payload && snackbar) {
      setState(
        produce((state: IStore) => {
          state.ui.snackbar = {
            isOpen: true,
            messageType: response.payload.type || 'error',
            message:
              response.payload.reason ||
              response.payload.message ||
              JSON.stringify(response.payload)
          }
        })
      )
      if (response.data.status) {
        return response.data
      }
    }
    if (response.status === 200) {
      setState(
        produce((state: IStore) => {
          state.disconnected = false
        })
      )
      return response.data || response
    }
    return setState(
      produce((state: IStore) => {
        state.ui.snackbar = {
          isOpen: true,
          messageType: 'error',
          message: response.error || JSON.stringify(response)
        }
      })
    )
  } catch (error: any) {
    if (error.message) {
      return setState(
        produce((state: IStore) => {
          state.ui.snackbar = {
            isOpen: true,
            messageType: 'error',
            message: JSON.stringify(error.message)
          }
        })
      )
    }
    setState(
      produce((state: IStore) => {
        state.ui.snackbar = {
          isOpen: true,
          messageType: 'error',
          message: JSON.stringify(error, null, 2)
        }
      })
    )
  }
  return true
}
