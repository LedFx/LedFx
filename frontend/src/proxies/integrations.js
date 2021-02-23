import { api } from 'utils/api';

export function getIntegrations() {
    return api.get(`/integrations`);
}

export function getIntegrationsStatuses() {
    return api.get(`/integrations`, { info: 'status' });
}

export function toggleIntegration(data) {
    return api.put(`/integrations`, data);
}

export function createIntegration(data) {
    return api.post(`/integrations`, data);
}

export function deleteIntegration(data) {
    // console.log('YZ', data);
    return api.delete(`/integrations`, data);
}

// QLC+ Proxies

export function getQLCInfo(integrationId) {
    console.log("getQLCInfo", integrationId);
    return api.get(`/integrations/qlc/${integrationId}`);
}

export function toggleQLCListener(integrationId, data) {
    return api.put(`/integrations/qlc/${integrationId}`, data);
}

export function createQLCListener(integrationId, data) {
    return api.post(`/integrations/qlc/${integrationId}`, data);
}

export function deleteQLCListener(integrationId, data) {
    return api.delete(`/integrations/qlc/${integrationId}`, data);
}

// Spotify proxies

export function getSpotifyTriggers(integrationId) {
    return api.get(`/integrations/spotify/${integrationId}`);
}

export function updateSpotifyTrigger(integrationId, data) {
    return api.put(`/integrations/spotify/${integrationId}`, data);
}

export function createSpotifyTrigger(integrationId, data) {
    return api.post(`/integrations/spotify/${integrationId}`, data);
}

export function deleteSpotifyTrigger(integrationId, data) {
    return api.delete(`/integrations/spotify/${integrationId}`, data);
}
