import {
    GET_PRESETS
} from 'actions'

export function presets(state = {}, action) {
    switch (action.type) {
        case GET_PRESETS:
            return action.presets;
        default:
            return state;
    }
}