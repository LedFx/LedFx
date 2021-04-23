import { createAction, handleActions } from 'redux-actions';
import * as displayProxies from 'proxies/display';
import * as effectsProxies from 'proxies/effects';
import { convertDictionaryToList } from 'utils/helpers';
import { effectReceived } from 'modules/selectedDisplay';

// Actions
const ACTION_ROOT = 'sceneManagement';
export const presetsFetching = createAction(`${ACTION_ROOT}/PRESETS_FETCHING`);
export const presetsFetched = createAction(`${ACTION_ROOT}/PRESETS_FETCHED`);
export const presetAdding = createAction(`${ACTION_ROOT}/PRESET_ADDING`);
export const presetAdded = createAction(`${ACTION_ROOT}/PRESET_ADDED`);
export const presetRemoving = createAction(`${ACTION_ROOT}/PRESET_REMOVING`);
export const presetRemoved = createAction(`${ACTION_ROOT}/PRESET_REMOVED`);

// Reducer
const INITIAL_STATE = {
    isLoading: false,
    isProcessing: false,
    defaultPresets: [],
    customPresets: [],
    effectType: '',
};

export default handleActions(
    {
        [presetsFetching]: state => ({
            ...state,
            isLoading: true,
        }),
        [presetsFetched]: (
            state,
            { payload, payload: { defaultPresets = [], customPresets = [], effectType }, error }
        ) => {
            return {
                ...state,
                defaultPresets: error ? [] : defaultPresets,
                customPresets: error ? [] : customPresets,
                effectType,
                isLoading: false,
                error: error ? payload.message : '',
            };
        },
        [presetAdding]: state => ({
            ...state,
            isProcessing: true,
        }),

        [presetAdded]: (state, { payload, payload: { id, name, config }, error }) => {
            const customPresets = [
                ...state.customPresets,
                {
                    id,
                    name,
                    config,
                },
            ];
            return {
                ...state,
                customPresets: error ? state.customPresets : customPresets,
                isProcessing: false,
                error: error ? payload.message : '',
            };
        },
        [presetRemoving]: state => ({
            ...state,
            isProcessing: true,
        }),

        [presetRemoved]: (state, { payload, payload: { id }, error }) => {
            const customPresets = [...state.customPresets].filter(c => c.id !== id);
            return {
                ...state,
                customPresets: error ? state.customPresets : customPresets,
                isProcessing: false,
                error: error ? payload.message : '',
            };
        },
    },
    INITIAL_STATE
);

export function getEffectPresets(effectType) {
    if (effectType) {
        return async dispatch => {
            dispatch(presetsFetching());
            try {
                const response = await effectsProxies.getEffectPresets(effectType);

                if (response.statusText === 'OK') {
                    const { default_presets, custom_presets, effect } = response.data;
                    const defaultPresets = convertDictionaryToList(default_presets);
                    const customPresets = convertDictionaryToList(custom_presets);
                    dispatch(presetsFetched({ defaultPresets, customPresets, effectType: effect }));
                }
            } catch (error) {
                dispatch(presetsFetched(error));
            }
        };
    }
}

export function addPreset(displayId, name) {
    return async dispatch => {
        dispatch(presetAdding());
        try {
            const { data, statusText } = await displayProxies.addPreset(displayId, { name });
            if (statusText === 'OK') {
                dispatch(presetAdded(data.preset));
            }
        } catch (error) {
            dispatch(presetAdded(error));
        }
    };
}
export function removePreset(effectId, payload) {
    return async dispatch => {
        dispatch(presetRemoving());
        try {
            const { statusText } = await effectsProxies.removeEffectPreset(effectId, payload);
            if (statusText === 'OK') {
                dispatch(presetRemoved({ id: payload.preset_id }));
            }
        } catch (error) {
            dispatch(presetRemoved(error));
        }
    };
}

export function activatePreset(displayId, category, effectId, presetId) {
    return async dispatch => {
        try {
            const request = {
                category: category,
                effect_id: effectId,
                preset_id: presetId,
            };

            const { data, statusText } = await displayProxies.updatePreset(displayId, request);
            if (statusText === 'OK') {
                dispatch(effectReceived(data.effect));
            }
        } catch (error) {
            dispatch(effectReceived(error));
        }
    };
}
