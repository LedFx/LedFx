import {
    GET_AUDIO_INPUTS,
    // SET_AUDIO_INPUT
} from 'actions'

export function settings(state = {}, action) {
    console.log(action)
    switch (action.type) {
        case GET_AUDIO_INPUTS:
            const audioDevices = action.audioDevices
            return {...state, audioDevices}
        default:
            return state
    }
}