import { createAction, handleActions } from 'redux-actions';
import Cookies from 'universal-cookie/es6';
import * as spotifyProxies from '../proxies/spotify';

// Actions
const ACTION_ROOT = 'spotify';
export const authFinished = createAction(`${ACTION_ROOT}/AUTH_FINISHED`);
export const authRefreshed = createAction(`${ACTION_ROOT}/AUTH_REFRESHED`);
export const playerStateUpdated = createAction(`${ACTION_ROOT}/PLAYER_STATE_UPDATED`);
export const audioFeaturesStateUpdated = createAction(`${ACTION_ROOT}/PLAYER_AUDIOFEATURES_UPDATED`);
export const cookiesChecked = createAction(`${ACTION_ROOT}/COOKIES_CHECKED`);
export const logoutAuthUpdated = createAction(`${ACTION_ROOT}/LOGOUT_UPDATED`);

// // Reducer
const INITIAL_STATE = {
    accessToken: '',
    refreshToken: '',
    logout: true,
    audioFeatures: {},
    playerState: {},
};

export default handleActions(
    {
        [cookiesChecked]: (state, { payload, payload: { accessToken, refreshToken } }) => {
            return {
                ...state,
                accessToken: accessToken,
                refreshToken: refreshToken,
            };
        },
        [authFinished]: (state, { payload, payload: { accessToken, refreshToken } }) => {
            return {
                ...state,
                accessToken: accessToken,
                refreshToken: refreshToken,
            };
        },
        [authRefreshed]: (state, { payload, payload: { accessToken, refreshToken } }) => {
            return {
                ...state,
                accessToken: accessToken,
                refreshToken: refreshToken,
            };
        },
        [audioFeaturesStateUpdated]: (state, { payload, payload: { audioFeatures } }) => {
            return {
                ...state,
                audioFeatures: payload,
            };
        },
        [playerStateUpdated]: (state, { payload, payload: { playerState } }) => {
            return {
                ...state,
                playerState: payload,
            };
        },

        [logoutAuthUpdated]: (
            state,
            { payload, payload: { logout, accessToken, refreshToken } }
        ) => {
            return {
                ...state,
                accessToken: accessToken,
                refreshToken: refreshToken,
                logout: logout,
            };
        },
    },
    INITIAL_STATE
);

export function checkCookiesForTokens() {
    console.log('checking');
    return dispatch => {
        const cookies = new Cookies();
        const tokens = {
            accessToken: cookies.get('access_token'),
            refreshToken: cookies.get('refresh_token'),
        };
        dispatch(cookiesChecked(tokens));
    };
}

export function finishAuth() {
    return async dispatch => {
        try {
            const tokens = await spotifyProxies.finishAuth();
            dispatch(authFinished(tokens));
        } catch (error) {
            console.log(error);
        }
    };
}

export function refreshAuth() {
    return async dispatch => {
        try {
            const tokens = await spotifyProxies.refreshAuth();
            if (tokens.accessToken) {
                dispatch(authRefreshed(tokens));
            }
        } catch (error) {
            console.log(error);
        }
    };
}

export function logoutAuth() {
    return async dispatch => {
        const check = spotifyProxies.logoutAuth();
        const cookies = new Cookies();
        const data = {
            logout: check,
            accessToken: cookies.get('access_token'),
            refreshToken: cookies.get('refresh_token'),
        };
        dispatch(logoutAuthUpdated(data));
    };
}

export function updatePlayerState(playerState) {
    return async dispatch => {
        try {
            const cookies = new Cookies();
            const access_token = cookies.get('access_token');

            const audioFeatures = await spotifyProxies.getTrackFeatures(
                playerState.track_window.current_track.id,
                access_token
            );

            dispatch(playerStateUpdated(playerState));
            //console.log('ID for audiofeatures', playerState.track_window.current_track.id);
        } catch (error) {
            console.log(error);
        }
        if (playerState.loading) {
            const cookies = new Cookies();
            const access_token = cookies.get('access_token');

            const audioFeatures = await spotifyProxies.getTrackFeatures(
                playerState.track_window.current_track.id,
                access_token
            );
            dispatch(audioFeaturesStateUpdated(audioFeatures));
            console.log('loading');
        }
    };
}

export function updateAudioFeatures(audioFeatures) {
    return dispatch => {
        try {
            dispatch(audioFeaturesStateUpdated(audioFeatures));
            console.log('Audiofeatures', audioFeatures);
        } catch (error) {
            console.log(error);
        }
    };
}

export const increaseSongTime = time => {
    return {
        type: 'INCREASE_SONG_TIME',
        time,
    };
};
