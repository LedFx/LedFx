import { createAction, handleActions } from 'redux-actions';
import * as settingProxies from 'proxies/settings';

// Actions
const ACTION_ROOT = 'settings';
export const audioInputsFetching = createAction(`${ACTION_ROOT}/AUDIO_DEVICES_FETCHING`);
export const audioInputsFetched = createAction(`${ACTION_ROOT}/AUDIO_DEVICES_FETCHED`);
export const audioInputSaved = createAction(`${ACTION_ROOT}/AUDIO_DEVICES_SAVED`);
export const audioInputSaving = createAction(`${ACTION_ROOT}/AUDIO_DEVICES_SAVING`);
export const configFetching = createAction(`${ACTION_ROOT}/CONFIG_FETCHING`);
export const configFetched = createAction(`${ACTION_ROOT}/CONFIG_FETCHED`);
export const updateDevices = createAction('settings/DEVICES_UPDATED');
export const updateDisplays = createAction('settings/DISPLAYS_UPDATED');

// Reducer
const INITIAL_STATE = {
    audioInputs: {
        isLoading: false,
        options: [],
        isSaving: false,
        value: '',
        error: '',
    },
    isLoading: false,
    devMode: false,
    port: '',
    host: '',
    devices: [],
    error: '',
};

export default handleActions(
    {
        [updateDevices]: (state, { payload }) => ({
            ...state,
            devices: payload,
        }),
        [updateDisplays]: (state, { payload }) => ({
            ...state,
            devices: payload,
        }),
        [audioInputsFetching]: state => ({
            ...state,
            audioInputs: {
                ...state.audioInputs,
                isLoading: true,
            },
        }),
        [audioInputsFetched]: (
            state,
            { payload, payload: { options = [], value = '' }, error }
        ) => ({
            ...state,
            audioInputs: {
                ...state.audioInputs,
                isLoading: false,
                options: error ? [] : options,
                value: error ? '' : value,
                error: error ? payload : '',
            },
        }),
        [audioInputSaving]: state => ({
            ...state,
            audioInputs: {
                ...state.audioInputs,
                isSaving: true,
            },
        }),
        [audioInputSaved]: (state, { payload, error }) => ({
            ...state,
            audioInputs: {
                ...state.audioInputs,
                value: error ? '' : payload,
                isSaving: false,
                error: error ? payload : '',
            },
        }),
        [configFetching]: state => ({
            ...state,
            isLoading: true,
        }),
        [configFetched]: (state, { payload, error }) => ({
            ...state,
            ...payload,
            isLoading: false,
            error: error ? payload : '',
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
            const value = audioInputs[active_device_index];
            dispatch(audioInputsFetched({ options, value }));
        } catch (error) {
            dispatch(audioInputsFetched(error));
        }
    };
}

export function setAudioInput({ value, index }) {
    return async dispatch => {
        try {
            dispatch(audioInputSaving());
            const response = await settingProxies.updateSelectedAudioInput({
                index: parseInt(index),
            });
            if (response.statusText !== 'OK') {
                throw new Error('Audio Input failed to update');
            }

            dispatch(audioInputSaved(value));
        } catch (error) {
            dispatch(audioInputSaved(error));
        }
    };
}

export function getConfig() {
    return async dispatch => {
        dispatch(configFetching());
        try {
            const response = await settingProxies.getSystemConfig();
            if (response.statusText !== 'OK') {
                throw new Error('Error fetching system config');
            }
            const responseInfo = await settingProxies.getSystemInfo();
            if (responseInfo.statusText !== 'OK') {
                throw new Error('Error fetching system config');
            }
            const { dev_mode: devMode, port, host, devices } = response.data.config;
            const { version } = responseInfo.data;
            dispatch(configFetched({ devMode, host, port, devices, version }));
        } catch (error) {
            dispatch(configFetched(error));
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
