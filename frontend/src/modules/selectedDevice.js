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
    effect: null,
};

export default handleActions(
    {
        [deviceRequested]: state => ({
            ...state,
            isDeviceLoading: true,
        }),
        [deviceReceived]: (state, { payload }) => ({
            ...state,
            isDeviceLoading: false,
            device: payload,
        }),
        [effectRequested]: state => ({
            ...state,
            isEffectLoading: true,
        }),
        [effectReceived]: (state, { payload }) => ({
            ...state,
            isEffectLoading: false,
            effect: payload,
        }),
    },
    INITIAL_STATE
);

export function clearDeviceEffect(deviceId) {
    return async dispatch => {
        const {
            statusText,
            data: { effect }
        } = await deviceProxies.deleteDeviceEffect(deviceId);
        console.log('clear device effect response', effect);
        if (statusText !== 'OK') {
            throw new Error(`Error Clearing Device:${deviceId} Effect`);
        }
        dispatch(effectReceived(effect));
    };
}

export function setDeviceEffect(deviceId, { type, config }) {
    return async (dispatch, getState) => {
        const currentEffect = getState().selectedDevice.effect;
        console.log('whats the curent device', currentEffect);
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

            console.log('setDevice effect response', effect);
            if (statusText !== 'OK') {
                throw new Error(`Error Clearing Device:${deviceId} Effect`);
            }
            dispatch(effectReceived(effect));
        } catch (error) {
            console.log('what the error for set effect', error.message);
        }
    };
}

export function loadDeviceInfo(deviceId) {
    console.log('whats the device id', deviceId);
    return async (dispatch, getState) => {
        try {
            let device = getState().devices.dictionary;

            console.log('waht the device here', device);

            dispatch(deviceRequested());
            device = await deviceProxies.getDevice(deviceId);
            dispatch(deviceReceived(device));

            dispatch(effectRequested());
            const {
                data: { effect },
            } = await deviceProxies.getDeviceEffect(deviceId);
            dispatch(effectReceived(effect));
        } catch (error) {
            console.log(error);
        }
    };
}
