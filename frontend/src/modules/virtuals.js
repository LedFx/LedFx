import { createAction, handleActions } from 'redux-actions'
import * as virtualsProxies from 'proxies/virtuals'
// Actions
const ACTION_ROOT = 'virtuals'

export const addVirtual = createAction(`${ACTION_ROOT}/VIRTUAL_ADD`)
export const renameVirtual = createAction(`${ACTION_ROOT}/VIRTUAL_RENAME`)
export const deleteVirtual = createAction(`${ACTION_ROOT}/VIRTUAL_DELETE`)
export const addSegment = createAction(`${ACTION_ROOT}/ADD_SEGMENT`)
export const changeSegment = createAction(`${ACTION_ROOT}/CHANGE_SEGMENT`)
export const deleteSegment = createAction(`${ACTION_ROOT}/DELETE_SEGMENT`)
export const getVirtualsPixel = createAction(`${ACTION_ROOT}/VIRTUALS_GET_PIXELS`)
export const postVirtuals = createAction(`${ACTION_ROOT}/VIRTUALS_SET`)

// Reducer
const INITIAL_STATE = {
    list: [
        {
            name: 'Loading virtuals...',
            pixel_count: 0,
            items: []
        }
    ]
}

export default handleActions(
    {
        [postVirtuals]: (state, { payload }) => {
            const newState = { list: payload.virtuals.list }
            return newState
        },
        [addVirtual]: (state, { payload }) => {
            return {
                ...state,
                list: [...state.list,
                {
                    name: payload.new,
                    pixel_count: 0,
                    items: []
                }
                ]
            }
        },
        [renameVirtual]: (state, { payload }) => {
            return {
                ...state, list: state.list.map(reduxItem => {
                    if (reduxItem.name === payload.old) {
                        reduxItem.name = payload.new
                    }
                    return reduxItem
                })
            }
        },
        [deleteVirtual]: (state, { payload }) => {
            return { ...state, list: state.list.filter(v => v.name !== payload) }
        },
        [addSegment]: (state, { payload }) => {
            const newState = {
                ...state, list: state.list.map(reduxItem => {
                    if (reduxItem.name === payload.virtual) {
                        reduxItem.items = [...reduxItem.items, payload.device]
                        reduxItem.pixel_count = reduxItem.pixel_count + payload.device.config.pixel_count
                    }
                    return reduxItem
                })
            }
            return newState
        },
        [changeSegment]: (state, { payload }) => {
            const newState = {
                ...state, list: state.list.map(reduxItem => {
                    if (reduxItem.name === payload.virtual) {
                        reduxItem.items.map(device => {
                            if (device.id === payload.device) {
                                device.led_start = payload.newValue[0]
                                device.led_end = payload.newValue[1]
                                device.used_pixel = payload.newValue[1] - payload.newValue[0] + 1
                            }

                            return device
                        })
                    }
                    reduxItem.pixel_count = reduxItem.items.map(d => d.used_pixel).reduce((sum, part) => sum + part)
                    return reduxItem
                })
            }
            return newState
        },
        [deleteSegment]: (state, { payload }) => {
            const newState = {
                ...state, list: state.list.map(reduxItem => {
                    if (reduxItem.name === payload.virtual) {
                        reduxItem.items = reduxItem.items.filter((device) => device.id !== payload.device.id)
                    }
                    reduxItem.pixel_count = reduxItem.items.map(d => d.used_pixel).reduce((sum, part) => sum + part, 0)
                    return reduxItem
                })
            }
            return newState
        },
    },
    INITIAL_STATE
)

export function getAsyncVirtuals() {
    return async dispatch => {
        try {
            const response = await virtualsProxies.getVirtuals()
            if (response.statusText === 'OK') {
                dispatch(postVirtuals(response.data))
            }
        } catch (error) {
            console.log(error)
        }
    }
}