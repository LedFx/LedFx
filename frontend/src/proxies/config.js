import { api } from 'utils/api';

export function getSystemConfig() {
    return api.get('/config').then(response => {
        return response.data.config;
    });
}
