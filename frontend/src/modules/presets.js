import { createAction, handleActions } from 'redux-actions';
import * as presetsProxies from 'proxies/presets';

// Actions
const ACTION_ROOT = 'presetManagement';
export const presetsFetching = createAction(`${ACTION_ROOT}/PRESETS_FETCHING`);
export const presetsFetched = createAction(`${ACTION_ROOT}/PRESETS_FETCHED`);

// Reducer
const INITIAL_STATE = {
    isLoading: false,
    dictionary: {},
    list: [],
};

export default handleActions(
    {
        [presetsFetching]: state => ({
            ...state,
            isLoading: true,
        }),
        [presetsFetched]: (state, { payload: { presets = {}, list = [], error = '' } }) => {
            console.log('what the payload on recived', presets);
            return {
                ...state,
                dictionary: !error ? presets : {},
                list: !error ? list : [],
                isLoading: false,
            };
        },
    },
    INITIAL_STATE
);

export function getPresets() {
    return async dispatch => {
        dispatch(presetsFetching());
        try {
            const response = await presetsProxies.getPresets();
            console.log('waht ths presets response', response);

            if (response.statusText === 'OK') {
                const { presets } = response.data;
                const list = convertPresetsDictionaryToList(presets);

                dispatch(presetsFetched({ presets, list }));
            }
        } catch (error) {
            console.log('Error fetching presests', error.message);
            dispatch(presetsFetched({ error: error.message }));
        }
    };
}

export const ADD_PRESET = 'ADD_PRESET';
export const DELETE_PRESET = 'DELETE_PRESET';
export const GET_PRESETS = 'GET_PRESETS';
export const ACTIVATE_PRESET = 'ACTIVATE_PRESET';
export const RENAME_PRESET = 'RENAME_PRESET';

export function addPreset(name) {
    return dispatch => {
        return presetsProxies
            .addPresets(name)
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
        return presetsProxies
            .deletePresets(id)
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
        presetsProxies.activatePresets(id).then(response =>
            dispatch({
                type: ACTIVATE_PRESET,
                response: response.data,
            })
        );
    };
}

export function renamePreset(id, name) {
    return dispatch => {
        presetsProxies.renamePreset({ id, name }).then(response =>
            dispatch({
                type: RENAME_PRESET,
                response: response.data,
            })
        );
    };
}

const convertPresetsDictionaryToList = (presets = {}) =>
    Object.keys(presets).map(key => {
        const currentPreset = presets[key];
        console.log('whats the preset', currentPreset);
        return {
            ...currentPreset,
            key,
            id: key,
            name: currentPreset.name,
        };
    });
