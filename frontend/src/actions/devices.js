import fetch from "cross-fetch";

const apiUrl = window.location.protocol + "//" + window.location.host + "/api";

export const REQUEST_DEVICE_LIST = "REQUEST_DEVICE_LIST";
export const RECEIVE_DEVICE_LIST = "RECEIVE_DEVICE_LIST";
export const RECEIVE_DEVICE_ENTRY = "RECEIVE_DEVICE_ENTRY";
export const REQUEST_DEVICE_UPDATE = "REQUEST_DEVICE_UPDATE";
export const RECEIVE_DEVICE_UPDATE = "RECEIVE_DEVICE_UPDATE";
export const RECEIVE_DEVICE_EFFECT_UPDATE = "RECEIVE_DEVICE_EFFECT_UPDATE";
export const INVALIDATE_DEVICE = "INVALIDATE_DEVICE";
export const SET_DEVICE_EFFECT = "SET_DEVICE_EFFECT";

function requestDeviceList() {
  return {
    type: REQUEST_DEVICE_LIST
  };
}

function receiveDeviceList(json) {
  return {
    type: RECEIVE_DEVICE_LIST,
    devices: json.devices,
    receivedAt: Date.now()
  };
}

function receiveDevice(json) {
  return {
    type: RECEIVE_DEVICE_ENTRY,
    device: json.device,
    delete: json.delete,
    receivedAt: Date.now()
  };
}

export function getSystemConfig() {
  return fetch(`${apiUrl}/config`)
      .then(response => response.json());
}

export function addDevice(type, config) {
  return dispatch => {
    const data = {
      type: type,
      config: config
    };
    fetch(`${apiUrl}/devices`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(data)
    })
      .then(response => response.json())
      .then(json => dispatch(receiveDevice(json)));
  };
}

export function deleteDevice(id) {
    let deleteJson = { delete: true, device: {id: id} }
    return dispatch => {
        fetch(`${apiUrl}/devices/${id}`, {
            method: 'DELETE'})
            .then(response => dispatch(receiveDevice(deleteJson)));
    }
}

export function fetchDeviceList() {
  return dispatch => {
    dispatch(requestDeviceList());
    return fetch(`${apiUrl}/devices`)
      .then(response => response.json())
      .then(json => dispatch(receiveDeviceList(json)));
  };
}

export function setDeviceEffect(deviceId, effectType, effectConfig) {
  return dispatch => {
    if (effectType)
    {
      fetch(`${apiUrl}/devices/${deviceId}/effects`, {
        method: "PUT",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          type: effectType,
          config: effectConfig
        })
      })
      .then(response => response.json())
      .then(json => dispatch(receiveDeviceEffectUpdate(deviceId, json)));
    }
    else
    {
      fetch(`${apiUrl}/devices/${deviceId}/effects`, {
        method: "DELETE"
      })
      .then(response => response.json())
      .then(json => dispatch(receiveDeviceEffectUpdate(deviceId, json)));
    }
  };
}

function invalidateDevice(deviceId) {
  return {
    type: INVALIDATE_DEVICE,
    deviceId
  };
}

function requestDeviceUpdate(deviceId) {
  return {
    type: REQUEST_DEVICE_UPDATE,
    deviceId
  };
}

function receiveDeviceUpdate(deviceId, json) {
  return {
    type: RECEIVE_DEVICE_UPDATE,
    deviceId,
    config: json.config.map(config => config),
    receivedAt: Date.now()
  };
}

function receiveDeviceEffectUpdate(deviceId, json) {
  return {
    type: RECEIVE_DEVICE_EFFECT_UPDATE,
    deviceId,
    effect: json.effect,
    receivedAt: Date.now()
  }; 
}

function fetchDevice(deviceId) {
  return dispatch => {
    dispatch(requestDeviceUpdate(deviceId));
    return fetch(`${apiUrl}/devices/${deviceId}`)
      .then(response => response.json())
      .then(json => dispatch(receiveDeviceUpdate(deviceId, json)))
  };
}

export function fetchDeviceEffects(deviceId) {
  return dispatch => {
    return fetch(`${apiUrl}/devices/${deviceId}/effects`)
      .then(response => response.json())
      .then(json => dispatch(receiveDeviceEffectUpdate(deviceId, json)));
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
