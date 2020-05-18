import { api } from 'utils/api';

export const GET_AUDIO_INPUTS = 'GET_AUDIO_INPUTS';
export const SET_AUDIO_INPUT = 'GET_AUDIO_INPUT';

export function setAudioDevice(index) {
    return dispatch => {
        const data = {
            index: parseInt(index),
        };
        api.put('/audio/devices', data)
            .then(response =>
                dispatch({
                    type: SET_AUDIO_INPUT,
                    response: response.data,
                })
            )
            .then(() => dispatch(getAudioDevices()));
    };
}

export function getAudioDevices() {
    return dispatch => {
        api.get('/audio/devices').then(response =>
            dispatch({
                type: GET_AUDIO_INPUTS,
                audioDevices: response.data,
                receivedAt: Date.now(),
            })
        );
    };
}
