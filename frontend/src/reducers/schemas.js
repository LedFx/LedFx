import { combineReducers } from 'redux'
import {
    RECEIVE_SCHEMAS,
} from '../actions'

export function schemas(state = {}, action) {
    switch (action.type) {
        case RECEIVE_SCHEMAS:
            return Object.assign({}, state, action.schemas)
        default:
            return state;
    }
}