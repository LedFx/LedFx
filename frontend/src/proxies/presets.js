import { api } from 'utils/api';

export function getPresets() {
    return api.get('/presets');
}
export function addPresets(name) {
    return api.post('/presets', { name });
}

export function deletePresets(id) {
    return api.delete('/presets', { data: { id } });
}

export function activatePresets(id) {
    return api.put('/presets', {
        id,
        action: 'activate',
    });
}
export function renamePreset({ id, name }) {
    return api.put('/presets', {
        action: 'rename',
        id,
        name,
    });
}
