import { GET_ALL_PRESETS, GET_DEVICE_PRESETS } from 'frontend/actions'

export function presets(state = {}, action) {
    switch (action.type) {
        case GET_ALL_PRESETS:
            return action.presets;
        case GET_DEVICE_PRESETS:
            return action.presets;
        default:
            return state;
    }
}