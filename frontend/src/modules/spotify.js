import { createAction, handleActions } from 'redux-actions';
import Cookies from 'universal-cookie/es6';
import * as spotifyProxies from '../proxies/spotify'


// Actions
const ACTION_ROOT = 'spotify';
export const authFinished = createAction(`${ACTION_ROOT}/AUTH_FINISHED`);
export const authRefreshed = createAction(`${ACTION_ROOT}/AUTH_REFRESHED`);
export const playerStateUpdated = createAction(`${ACTION_ROOT}/PLAYER_STATE_UPDATED`);
export const cookiesChecked = createAction(`${ACTION_ROOT}/COOKIES_CHECKED`);

// // Reducer
const INITIAL_STATE = {
    accessToken: '',
    refreshToken: '',
    playerState: {},

}

export default handleActions({
    [cookiesChecked]: (state, { payload, payload: { accessToken, refreshToken } }) => {
        return {
            ...state,
            accessToken: accessToken,
            refreshToken: refreshToken
        };
    },
    [authFinished]: (state, { payload, payload: { accessToken, refreshToken } }) => {
        return {
            ...state,
            accessToken: accessToken,
            refreshToken: refreshToken
        };
    },
    [authRefreshed]: (state, { payload, payload: { accessToken, refreshToken } }) => {
        return {
            ...state,
            accessToken: accessToken,
            refreshToken: refreshToken
        };
    },
    [playerStateUpdated]: (state, { payload, payload: { playerState } }) => {
        console.log(payload)
        return {
            ...state,
            playerState: payload
        };
    },
}, INITIAL_STATE)

export function checkCookiesForTokens() {
    console.log('checking')
    return dispatch => {
        const cookies = new Cookies();
        const tokens = {
            accessToken: cookies.get('access_token'),
            refreshToken: cookies.get('refresh_token'),
        }
        dispatch(cookiesChecked(tokens))
    }
}

export function finishAuth() {
    return async dispatch => {
        try {
            const tokens = await spotifyProxies.finishAuth()
            dispatch(authFinished(tokens))
        } catch (error) {
            console.log(error)
        }
    }
}

export function refreshAuth() {
    return async dispatch => {
        try {
            const tokens = await spotifyProxies.refreshAuth()
            if (tokens.accessToken) {
                dispatch(authRefreshed(tokens))
            }
        } catch (error) {
            console.log(error)
        }
    }
}

export function updatePlayerState(playerState) {
    return dispatch => {
        try {
            dispatch(playerStateUpdated(playerState))
        } catch (error) {
            console.log(error)
        }
    }
}