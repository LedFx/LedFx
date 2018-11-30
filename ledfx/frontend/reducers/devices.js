import {
    REQUEST_DEVICE_LIST,
    RECEIVE_DEVICE_LIST,
    INVALIDATE_DEVICE,
    REQUEST_DEVICE_UPDATE,
    RECEIVE_DEVICE_UPDATE,
    RECEIVE_DEVICE_EFECT_UPDATE,
    RECEIVE_DEVICE_ENTRY
} from 'frontend/actions'

function device(
    state = {
        isFetching: false,
        didInvalidate: false,
        config: {},
        effects: {},
    },
    action
) {
    switch (action.type) {
        case INVALIDATE_DEVICE:
            return {...state, didInvalidate: true }
        case REQUEST_DEVICE_UPDATE:
            return {
                ...state, 
                isFetching: true,
                didInvalidate: false
            }
        case RECEIVE_DEVICE_UPDATE:
            return {
                ...state, 
                isFetching: false,
                didInvalidate: false,
                config: action.config,
                lastUpdated: action.receivedAt
            }
        case RECEIVE_DEVICE_EFECT_UPDATE:
            return {
                ...state, 
                effects: action.effects, 
                lastUpdated: action.receivedAt
            }
            // return Object.assign({}, state, {
            //     effects: action.effects,
            //     lastUpdated: action.receivedAt
            // })
        default:
            return state
    }
}

function deviceList(state = {}, action) {
    switch (action.type) {
        case REQUEST_DEVICE_LIST:
            return state;
        case RECEIVE_DEVICE_LIST:
            return Object.assign({}, state, action.devices)
        case RECEIVE_DEVICE_ENTRY:
            if (action.delete) {
                let newState = state;
                delete newState[action.device.id]
                return newState
            } else {
                let newState = state
                newState[action.device.id] = action.device
                return newState
            }
        default:
            return state;
    }
}

export function devicesById(state = {}, action) {
    switch (action.type) {
        case INVALIDATE_DEVICE:
        case REQUEST_DEVICE_UPDATE:
        case RECEIVE_DEVICE_UPDATE:
        case RECEIVE_DEVICE_EFECT_UPDATE:
            return Object.assign({}, state, {
                [action.deviceId]: device(state[action.deviceId], action)
            })
        case REQUEST_DEVICE_LIST:
        case RECEIVE_DEVICE_LIST:
        case RECEIVE_DEVICE_ENTRY:
            return Object.assign({}, state, deviceList(state, action))
        default:
            return state
    }
}