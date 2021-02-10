import { createAction, handleActions } from 'redux-actions';
import * as displayProxies from 'proxies/display';
import { showdynSnackbar } from './ui';
// Actions
const ACTION_ROOT = 'selectedDisplay';

export const displayRequested = createAction(`${ACTION_ROOT}/DISPLAY_REQUESTED`);
export const displayReceived = createAction(`${ACTION_ROOT}/DISPLAY_RECEIVED`);
export const effectRequested = createAction(`${ACTION_ROOT}/DISPLAY_EFFECT_REQUESTED`);
export const effectReceived = createAction(`${ACTION_ROOT}/DISPLAY_EFFECT_RECEIVED`);

// Reducer
const INITIAL_STATE = {
    isDisplayLoading: false,
    display: null,
    isEffectLoading: false,
    effect: {},
};

export default handleActions(
    {
        [displayRequested]: state => ({
            ...state,
            isDisplayLoading: true,
        }),
        [displayReceived]: (state, { payload, error }) => ({
            ...state,
            isDisplayLoading: false,
            display: error ? null : payload,
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

export function clearDisplayEffect(displayId) {
    return async dispatch => {
        try {
            const {
                statusText,
                data: { effect },
            } = await displayProxies.deleteDisplayEffect(displayId);
            if (statusText !== 'OK') {
                throw new Error(`Error Clearing Display:${displayId} Effect`);
            }
            dispatch(effectReceived(effect));
        } catch (error) {
            dispatch(effectReceived(error));
        }
    };
}

export function setDisplayEffect(displayId, { type, config }) {
    return async (dispatch, getState) => {
        const currentEffect = getState().selectedDisplay.effect;
        const proxy = currentEffect.type
            ? displayProxies.updateDisplayEffect
            : displayProxies.setDisplayEffect;
        try {
            const {
                statusText,
                data: { effect, payload },
            } = await proxy(displayId, {
                type,
                config,
            });
            if (payload) {
                dispatch(
                    showdynSnackbar({
                        message: payload.reason,
                        type: payload.type,
                    })
                );
                dispatch(clearDisplayEffect(displayId));
            }
            if (statusText !== 'OK') {
                throw new Error(`Error setting Display:${displayId} Effect`);
            }
            if (!payload) dispatch(effectReceived(effect));
        } catch (error) {
            dispatch(effectReceived(error));
        }
    };
}

export function loadDisplayInfo(displayId) {
    return async (dispatch, getState) => {
        try {
            let display = getState().displays.dictionary;
            dispatch(displayRequested());
            display = await displayProxies.getDisplay(displayId);
            dispatch(displayReceived(display));

            dispatch(effectRequested());
            const {
                data: { effect },
            } = await displayProxies.getDisplayEffect(displayId);
            dispatch(effectReceived(effect));
        } catch (error) {
            dispatch(effectReceived(error));
        }
    };
}
