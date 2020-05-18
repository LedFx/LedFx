import { api } from 'utils/api';

export function getDevices() {
    return api.get('/devices').then(response => {
        const devices = response.data.devices;
        return Object.keys(devices).map(key => {
            return {
                key: key,
                id: key,
                name: devices[key].name,
                config: devices[key],
            };
        });
    });
}

export function deleteDevice(device_id) {
    return api.delete(`/devices/${device_id}`);
}

export function updateDevice(config) {
    return api.put('/devices', config);
}

export function createDevice(config) {
    return api.post('/devices', config);
}

export function getDevice(device_id) {
    return api.get(`/devices/${device_id}`).then(response => {
        const device = response.data;
        return {
            key: device_id,
            id: device_id,
            name: device.name,
            config: device,
        };
    });
}

export function getDeviceEffects(device_id) {
    return api.get(`devices/${device_id}/effects`);
}

export function deleteDeviceEffects(device_id) {
    return api.delete(`devices/${device_id}/effects`);
}
