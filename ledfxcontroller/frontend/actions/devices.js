import fetch from 'cross-fetch'

const apiUrl = window.location.protocol + '//' + window.location.host + '/api';

export const REQUEST_DEVICE_LIST = 'REQUEST_DEVICE_LIST'
export const RECEIVE_DEVICE_LIST = 'RECEIVE_DEVICE_LIST'
export const REQUEST_DEVICE_UPDATE = 'REQUEST_DEVICE_UPDATE'
export const RECEIVE_DEVICE_UPDATE = 'RECEIVE_DEVICE_UPDATE'
export const INVALIDATE_DEVICE = 'INVALIDATE_DEVICE'
export const SET_DEVICE_EFFECT = 'SET_DEVICE_EFFECT'

function requestDeviceList() {
    return {
        type: REQUEST_DEVICE_LIST
    }
}

function receiveDeviceList(json) {
    return {
        type: RECEIVE_DEVICE_LIST,
        devices: json.devices,
        receivedAt: Date.now()
    }
}

export function fetchDeviceList() {
    return dispatch => {
        dispatch(requestDeviceList())
        return fetch(`${apiUrl}/devices`)
            .then(response => response.json())
            .then(json => dispatch(receiveDeviceList(json)))
    }
}

export function setDeviceEffect(deviceId, effectType, effectConfig) {

    return dispatch => {
        const data = {
            type: effectType,
            config: effectConfig,
        }
        fetch(`${apiUrl}/devices/${deviceId}/effects`, {
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
            })
    }
    // return dispatch => {
    //     dispatch(requestPosts(deviceId))
    //     return fetch(`${apiUrl}/devices/${deviceId}`)
    //         .then(response => response.json())
    //         .then(json => dispatch(receiveDeviceUpdate(deviceId, json)))
    // }
    // return {
    //     type: SET_DEVICE_EFFECT,
    //     deviceId,
    //     effectType,
    //     effectConfig
    // }
}

function invalidateDevice(deviceId) {
    return {
        type: INVALIDATE_DEVICE,
        deviceId
    }
}

function requestDeviceUpdate(deviceId) {
    return {
        type: REQUEST_DEVICE_UPDATE,
        deviceId
    }
}

function receiveDeviceUpdate(deviceId, json) {
    return {
        type: RECEIVE_DEVICE_UPDATE,
        deviceId,
        config: json.config.map(config => config),
        receivedAt: Date.now()
    }
}

function fetchDevice(deviceId) {
    return dispatch => {
        dispatch(requestPosts(deviceId))
        return fetch(`${apiUrl}/devices/${deviceId}`)
            .then(response => response.json())
            .then(json => dispatch(receiveDeviceUpdate(deviceId, json)))
    }
}

function shouldFetchDevice(state, deviceId) {
    const device = state.devicesById[deviceId]
    if (!device) {
        return true
    } else if (device.isFetching) {
        return false
    } else {
        return device.didInvalidate
    }
}

export function fetchDeviceIfNeeded(deviceId) {
    return (dispatch, getState) => {
        if (shouldFetchDevice(getState(), deviceId)) {
            return dispatch(fetchDevice(deviceId))
        }
    }
}