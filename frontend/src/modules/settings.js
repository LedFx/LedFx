import { createAction, handleActions } from 'redux-actions';
import * as settingProxies from 'proxies/settings';

// Actions
const ACTION_ROOT = 'settings';
export const audioInputsFetching = createAction(`${ACTION_ROOT}/AUDIO_DEVICES_FETCHING`);
export const audioInputsFetched = createAction(`${ACTION_ROOT}/AUDIO_DEVICES_FETCHED`);
export const audioInputSaved = createAction(`${ACTION_ROOT}/AUDIO_DEVICES_SAVED`);
export const audioInputSaving = createAction(`${ACTION_ROOT}/AUDIO_DEVICES_SAVING`);

// Reducer
const INITIAL_STATE = {
    audioInputs: {
        isLoading: false,
        options: [],
        isSaving: false,
        value: '',
        error: '',
    },
};

export default handleActions(
    {
        [audioInputsFetching]: state => ({
            ...state,
            audioInputs: {
                ...state.audioInputs,
                isLoading: true,
            },
        }),
        [audioInputsFetched]: (state, { payload: { options = [], value = '', error = '' } }) => ({
            ...state,
            audioInputs: {
                ...state.audioInputs,
                isLoading: false,
                options: error ? [] : options,
                value: error ? null : value,
                error,
            },
        }),
        [audioInputSaving]: state => ({
            ...state,
            audioInputs: {
                ...state.audioInputs,
                isSaving: true,
            },
        }),
        [audioInputSaved]: (state, { payload: { value = '', error = '' } }) => ({
            ...state,
            audioInputs: {
                ...state.audioInputs,
                value: error ? '' : value,
                isSaving: false,
                error,
            },
        }),
    },
    INITIAL_STATE
);

export function getAudioInputs() {
    return async dispatch => {
        dispatch(audioInputsFetching());
        try {
            const response = await settingProxies.getAudioInputs();
            if (response.statusText !== 'OK') {
                throw new Error('Error fetching audio Inputs');
            }

            const { devices: audioInputs, active_device_index } = response.data;
            const options = convertAudioInputsToList(audioInputs);
            const value = audioInputs[active_device_index]
            dispatch(audioInputsFetched({ options, value }));
        } catch (error) {
            console.log('Error fetching audio devices', error.message);
            dispatch(audioInputsFetched({ error: error.message }));
        }
    };
}

export function setAudioInput({ value, index }) {
    return async dispatch => {
        console.log('is this an int', value, index);

        try {
            dispatch(audioInputSaving());
            const response = await settingProxies.updateSelectedAudioInput({
                index: parseInt(index),
            });
            if (response.statusText !== 'OK') {
                throw new Error('Audio Input failed to update');
            }

            dispatch(audioInputSaved({ value }));
        } catch (error) {
            dispatch(audioInputSaved({ error: error.message }));
        }
    };
}

const convertAudioInputsToList = audioInputs =>
    Object.keys(audioInputs).map(key => {
        return {
            index: key,
            value: audioInputs[key],
        };
    });
