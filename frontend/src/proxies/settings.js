import { api } from 'utils/api';

export function shutdown() {
    return api.post('/power', {
        timeout: 0,
        action: 'shutdown',
    });
}
export function restart() {
    return api.post('/power', {
        timeout: 0,
        action: 'restart',
    });
}
export function getSystemConfig() {
    return api.get('/config');
}

export function deleteSystemConfig() {
    return api.delete('/config');

}
export function importSystemConfig(config) {
    return api.post('/config', config);
}
export function setSystemConfig(config) {
    return api.put('/config', config);
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
