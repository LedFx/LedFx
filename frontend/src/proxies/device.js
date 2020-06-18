import { api } from 'utils/api';

export function getDevices() {
    return api.get('/devices');
}

export function deleteDevice(deviceId) {
    return api.delete(`/devices/${deviceId}`);
}

export function updateDevice(id, data) {
    return api.put(`/devices/${id}`, data);
}

export function createDevice(config) {
    return api.post('/devices', config);
}

export function getDevice(deviceId) {
    return api.get(`/devices/${deviceId}`).then(response => {
        const device = response.data;
        return {
            key: deviceId,
            id: deviceId,
            name: device.name,
            config: device,
        };
    });
}

export function getDeviceEffect(deviceId) {
    return api.get(`devices/${deviceId}/effects`);
}

export function setDeviceEffect(deviceId, data) {
    return api.put(`devices/${deviceId}/effects`, data);
}

export function deleteDeviceEffect(deviceId) {
    return api.delete(`devices/${deviceId}/effects`);
}
