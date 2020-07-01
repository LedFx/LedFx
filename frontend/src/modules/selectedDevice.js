import { createAction, handleActions } from 'redux-actions';
import * as deviceProxies from 'proxies/device';

// Actions
const ACTION_ROOT = 'selectedDevice';

export const deviceRequested = createAction(`${ACTION_ROOT}/DEVICE_REQUESTED`);
export const deviceReceived = createAction(`${ACTION_ROOT}/DEVICE_RECEIVED`);
export const effectRequested = createAction(`${ACTION_ROOT}/DEVICE_EFFECT_REQUESTED`);
export const effectReceived = createAction(`${ACTION_ROOT}/DEVICE_EFFECT_RECEIVED`);

// Reducer
const INITIAL_STATE = {
    isDeviceLoading: false,
    device: null,
    isEffectLoading: false,
    effect: {},
};

export default handleActions(
    {
        [deviceRequested]: state => ({
            ...state,
            isDeviceLoading: true,
        }),
        [deviceReceived]: (state, { payload, error }) => ({
            ...state,
            isDeviceLoading: false,
            device: error ? null : payload,
            error: error ? payload.message : '',
        }),
        [effectRequested]: state => ({
            ...state,
            isEffectLoading: true,
        }),
        [effectReceived]: (state, { payload, error }) => ({
            ...state,
            isEffectLoading: false,
            effect: error ? {} : payload,
            error: error ? payload.message : '',
        }),
    },
    INITIAL_STATE
);

export function clearDeviceEffect(deviceId) {
    return async dispatch => {
        try {
            const {
                statusText,
                data: { effect },
            } = await deviceProxies.deleteDeviceEffect(deviceId);
            if (statusText !== 'OK') {
                throw new Error(`Error Clearing Device:${deviceId} Effect`);
            }
            dispatch(effectReceived(effect));
        } catch (error) {
            dispatch(effectReceived(error));
        }
    };
}

export function setDeviceEffect(deviceId, { type, config }) {
    return async (dispatch, getState) => {
        const currentEffect = getState().selectedDevice.effect;
        const proxy = currentEffect.type
            ? deviceProxies.updateDeviceEffect
            : deviceProxies.setDeviceEffect;
        try {
            const {
                statusText,
                data: { effect },
            } = await proxy(deviceId, {
                type,
                config,
            });

            if (statusText !== 'OK') {
                throw new Error(`Error Clearing Device:${deviceId} Effect`);
            }
            dispatch(effectReceived(effect));
        } catch (error) {
            dispatch(effectReceived(error));
        }
    };
}

export function loadDeviceInfo(deviceId) {
    return async (dispatch, getState) => {
        try {
            let device = getState().devices.dictionary;
            dispatch(deviceRequested());
            device = await deviceProxies.getDevice(deviceId);
            dispatch(deviceReceived(device));

            dispatch(effectRequested());
            const {
                data: { effect },
            } = await deviceProxies.getDeviceEffect(deviceId);
            dispatch(effectReceived(effect));
        } catch (error) {
            dispatch(effectReceived(error));
        }
    };
}
