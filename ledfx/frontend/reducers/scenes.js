import {
    GET_PRESETS
} from 'frontend/actions'

export function scenes(state = {}, action) {
    switch (action.type) {
        case GET_PRESETS:
            return action.scenes;
        default:
            return state;
    }
}