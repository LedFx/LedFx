import { api } from 'utils/api';

export function getEffectPresets(effectId) {
    return api.get(`effects/${effectId}/presets`);
}

export function updateEffectPreset(effectId, data) {
    return api.put(`effects/${effectId}/presets`, data);
}

export function addEffectPreset(effectId, data) {
    return api.post(`effects/${effectId}/presets`, data);
}
