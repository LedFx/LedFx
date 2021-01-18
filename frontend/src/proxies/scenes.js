import { api } from 'utils/api';

export function getScenes() {
    return api.get('/scenes');
}
export function addScenes(name) {
    return api.post('/scenes', { name });
}

export function deleteScenes(id) {
    return api.delete('/scenes', { data: { id } });
}

export function activateScenes(id) {
    return api.put('/scenes', {
        id,
        action: 'activate',
    });
}
export function renameScene({ id, name }) {
    return api.put('/scenes', {
        action: 'rename',
        id,
        name,
    });
}
