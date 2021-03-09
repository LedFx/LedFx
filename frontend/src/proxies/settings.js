import { api } from 'utils/api';

export function getSystemConfig() {
    return api.get('/config');
}

export function getSystemInfo() {
    return api.get('/info');
}

export function getAudioInputs() {
    return api.get('/audio/devices');
}
export function updateSelectedAudioInput(data) {
    return api.put('/audio/devices', data);
}
