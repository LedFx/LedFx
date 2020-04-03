import {
    GET_SCENES
} from 'frontend/actions'

export function scenes(state = {}, action) {
    switch (action.type) {
        case GET_SCENES:
            return action.scenes;
        default:
            return state;
    }
}