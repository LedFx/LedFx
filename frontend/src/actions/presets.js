import { api } from 'utils/api';

export const ADD_PRESET = 'ADD_PRESET';
export const DELETE_PRESET = 'DELETE_PRESET';
export const GET_PRESETS = 'GET_PRESETS';
export const ACTIVATE_PRESET = 'ACTIVATE_PRESET';
export const RENAME_PRESET = 'RENAME_PRESET';

export function addPreset(name) {
    return dispatch => {
        const data = {
            name: name,
        };
        return api
            .post('/presets', data)
            .then(response =>
                dispatch({
                    type: ADD_PRESET,
                    response: response.data,
                })
            )
            .then(() => dispatch(getPresets()));
    };
}

export function deletePreset(id) {
    return dispatch => {
        const data = {
            id: id,
        };
        return api
            .delete('/presets', data)
            .then(response =>
                dispatch({
                    type: DELETE_PRESET,
                    response: response.data,
                })
            )
            .then(() => dispatch(getPresets()));
    };
}

export function activatePreset(id) {
    return dispatch => {
        const data = {
            id: id,
            action: 'activate',
        };
        api.put('/presets', data).then(response =>
            dispatch({
                type: ACTIVATE_PRESET,
                response: response.data,
            })
        );
    };
}

export function renamePreset(id, name) {
    return dispatch => {
        const data = {
            id: id,
            action: 'rename',
            name: name,
        };
        api.put('/presets', data).then(response =>
            dispatch({
                type: RENAME_PRESET,
                response: response.data,
            })
        );
    };
}

export function getPresets() {
    return dispatch => {
        api.get('/presets').then(response =>
            dispatch({
                type: GET_PRESETS,
                presets: response.data.presets,
                receivedAt: Date.now(),
            })
        );
    };
}
