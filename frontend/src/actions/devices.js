import * as deviceProxies from 'proxies/device';

export const REQUEST_DEVICE_LIST = 'REQUEST_DEVICE_LIST';
export const RECEIVE_DEVICE_LIST = 'RECEIVE_DEVICE_LIST';
export const RECEIVE_DEVICE_ENTRY = 'RECEIVE_DEVICE_ENTRY';
export const REQUEST_DEVICE_UPDATE = 'REQUEST_DEVICE_UPDATE';
export const RECEIVE_DEVICE_UPDATE = 'RECEIVE_DEVICE_UPDATE';
export const RECEIVE_DEVICE_EFFECT_UPDATE = 'RECEIVE_DEVICE_EFFECT_UPDATE';
export const INVALIDATE_DEVICE = 'INVALIDATE_DEVICE';
export const SET_DEVICE_EFFECT = 'SET_DEVICE_EFFECT';

function requestDeviceList() {
    return {
        type: REQUEST_DEVICE_LIST,
    };
}

function receiveDeviceList(json) {
    return {
        type: RECEIVE_DEVICE_LIST,
        devices: json.devices,
        receivedAt: Date.now(),
    };
}

function receiveDevice(json) {
    return {
        type: RECEIVE_DEVICE_ENTRY,
        device: json.device,
        delete: json.delete,
        receivedAt: Date.now(),
    };
}

export function addDevice(type, config) {
    return dispatch => {
        const data = {
            type: type,
            config: config,
        };
        deviceProxies.createDevice(data).then(response => dispatch(receiveDevice(response.data)));
    };
}

export function deleteDevice(id) {
    let deleteJson = { delete: true, device: { id: id } };
    return dispatch => {
        deviceProxies.deleteDevice(id).then(response => dispatch(receiveDevice(deleteJson)));
    };
}

export function fetchDeviceList() {
    return dispatch => {
        dispatch(requestDeviceList());
        return deviceProxies.getDevices().then(response => {
            console.log('waht ths devies response', response);
            dispatch(receiveDeviceList(response));
        });
    };
}

export function setDeviceEffect(deviceId, effectType, effectConfig) {
    return dispatch => {
        if (effectType) {
            deviceProxies
                .getDeviceEffects(deviceId, {
                    type: effectType,
                    config: effectConfig,
                })
                .then(response => dispatch(receiveDeviceEffectUpdate(deviceId, response.data)));
        } else {
            deviceProxies
                .deleteDeviceEffects(deviceId)
                .then(response => dispatch(receiveDeviceEffectUpdate(deviceId, response.data)));
        }
    };
}

function invalidateDevice(deviceId) {
    return {
        type: INVALIDATE_DEVICE,
        deviceId,
    };
}

function requestDeviceUpdate(deviceId) {
    return {
        type: REQUEST_DEVICE_UPDATE,
        deviceId,
    };
}

function receiveDeviceUpdate(deviceId, json) {
    return {
        type: RECEIVE_DEVICE_UPDATE,
        deviceId,
        config: json.config.map(config => config),
        receivedAt: Date.now(),
    };
}

function receiveDeviceEffectUpdate(deviceId, json) {
    return {
        type: RECEIVE_DEVICE_EFFECT_UPDATE,
        deviceId,
        effect: json.effect,
        receivedAt: Date.now(),
    };
}

function fetchDevice(deviceId) {
    return dispatch => {
        dispatch(requestDeviceUpdate(deviceId));
        return deviceProxies
            .getDevice(deviceId)
            .then(response => dispatch(receiveDeviceUpdate(deviceId, response.data)));
    };
}

export function fetchDeviceEffects(deviceId) {
    return dispatch => {
        return deviceProxies
            .getDeviceEffects(deviceId)
            .then(response => dispatch(receiveDeviceEffectUpdate(deviceId, response.data)));
    };
}

function shouldFetchDevice(state, deviceId) {
    const device = state.devicesById[deviceId];
    if (!device) {
        return true;
    } else if (device.isFetching) {
        return false;
    } else {
        return device.didInvalidate;
    }
}

export function fetchDeviceIfNeeded(deviceId) {
    return (dispatch, getState) => {
        if (shouldFetchDevice(getState(), deviceId)) {
            return dispatch(fetchDevice(deviceId));
        }
    };
}
