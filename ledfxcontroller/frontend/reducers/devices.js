import {
    REQUEST_DEVICE_LIST,
    RECEIVE_DEVICE_LIST,
    INVALIDATE_DEVICE,
    REQUEST_DEVICE_UPDATE,
    RECEIVE_DEVICE_UPDATE
} from 'frontend/actions'

function device(
    state = {
        isFetching: false,
        didInvalidate: false,
        config: {}
    },
    action
) {
    switch (action.type) {
        case INVALIDATE_DEVICE:
            return Object.assign({}, state, {
                didInvalidate: true
            })
        case REQUEST_DEVICE_UPDATE:
            return Object.assign({}, state, {
                isFetching: true,
                didInvalidate: false
            })
        case RECEIVE_DEVICE_UPDATE:
            return Object.assign({}, state, {
                isFetching: false,
                didInvalidate: false,
                config: action.config,
                lastUpdated: action.receivedAt
            })
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
        default:
            return state;
    }
}

export function devicesById(state = {}, action) {
    switch (action.type) {
        case INVALIDATE_DEVICE:
        case REQUEST_DEVICE_UPDATE:
        case RECEIVE_DEVICE_UPDATE:
            return Object.assign({}, state, {
                [action.deviceId]: device(state[action.deviceId], action)
            })
        case REQUEST_DEVICE_LIST:
        case RECEIVE_DEVICE_LIST:
            return Object.assign({}, state, deviceList(state, action))
        default:
            return state
    }
}