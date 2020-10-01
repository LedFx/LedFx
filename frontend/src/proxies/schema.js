import { api } from 'utils/api';

export function getSchemas() {
    return api.get('/schema');
}