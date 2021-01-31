import { api } from 'utils/api';

export function getDisplays() {
    return api.get('/displays');
}

// If display id is given in config, this will UPDATE an existing display
// If no id is given, this will create a new display
export function createDisplay(config) {
    return api.post('/displays', config);
}
export function updateDisplay(displayId, config) {
    return api.post('/displays', {
        id: displayId,
        config: config,
    });
}

// Get info on a display, including its segments
export function getDisplay(displayId) {
    return api.get(`/displays/${displayId}`).then(response => {
        const display = response.data;
        return {
            key: displayId,
            id: displayId,
            name: display.name,
            config: display,
        };
    });
}

// Set a display to on or off using {"active": true/false}
export function toggleDisplay(displayId, data) {
    return api.put(`/displays/${displayId}`, data);
}

// Update a display's segments
export function updateDisplaySegments(displayId, data) {
    return api.post(`/displays/${displayId}`, data);
}

// Delete a display
export function deleteDisplay(displayId) {
    return api.delete(`/displays/${displayId}`);
}

export function getDisplayEffect(displayId) {
    return api.get(`displays/${displayId}/effects`);
}

export function setDisplayEffect(displayId, data) {
    return api.post(`displays/${displayId}/effects`, data);
}

export function updateDisplayEffect(displayId, data) {
    return api.put(`displays/${displayId}/effects`, data);
}

export function deleteDisplayEffect(displayId) {
    return api.delete(`displays/${displayId}/effects`);
}

export function getDisplayPresets(displayId) {
    return api.get(`displays/${displayId}/presets`);
}

export function updatePreset(displayId, data) {
    return api.put(`displays/${displayId}/presets`, data);
}

export function addPreset(displayId, data) {
    return api.post(`displays/${displayId}/presets`, data);
}
