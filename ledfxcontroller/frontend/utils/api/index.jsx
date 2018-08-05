import axios from "axios";

const url = window.location.protocol + '//' + window.location.host + '/api/';

function callApi(method, api, data) {
    return axios({
        method: method,
        url: url + api,
        data: data
    });
}

function getDevices() {
    return callApi('get', 'devices').then(response => {
        const devices = response.data.devices
        return Object.keys(devices).map(key => {
            return {
                key: key,
                id: key,
                name: devices[key].name,
                config: devices[key]
            }
        })
    })
}

function deleteDevice(device_id) {
    return callApi('delete', 'devices/' + device_id)
}

function addDevice(config) {
    return callApi('put', 'devices', config)
}

function getDevice(device_id) {
    return callApi('get', 'devices/' + device_id).then(response => {
        const device = response.data
        return {
            key: device_id,
            id: device_id,
            name: device.name,
            config: device
        }
    })
}

export { callApi, getDevices, deleteDevice, addDevice, getDevice }