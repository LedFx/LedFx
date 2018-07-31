import { combineReducers } from 'redux'
import {
    REQUEST_EFFECT_LIST,
    RECEIVE_EFFECT_LIST,
} from 'frontend/actions'

export function effects(state = [], action) {
    switch (action.type) {
        case RECEIVE_EFFECT_LIST:
            return Object.assign({}, state, action.effects)
        default:
            return state;
    }
}