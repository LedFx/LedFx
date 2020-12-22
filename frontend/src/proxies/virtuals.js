import { api } from 'utils/api';

export function getVirtuals() {
    return api.get('/virtuals');
}
export function setVirtuals({ virtuals }) {
    return api.post('/virtuals', { virtuals: virtuals });
}

// export function deleteVirtuals(id) {
//     return api.delete('/virtuals', { data: { id } });
// }

// export function activateVirtuals(id) {
//     return api.put('/virtuals', {
//         id,
//         action: 'activate',
//     });
// }
// export function renameScene({ id, virtual }) {
//     return api.put('/virtuals', {
//         action: 'rename',
//         id,
//         virtual,
//     });
// }
