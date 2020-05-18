import { api } from 'utils/api';

export const REQUEST_SCHEMAS = 'REQUEST_SCHEMAS';
export const RECEIVE_SCHEMAS = 'RECEIVE_SCHEMAS';

function requestSchemas() {
    return {
        type: REQUEST_SCHEMAS,
    };
}

function receiveSchemas(json) {
    return {
        type: RECEIVE_SCHEMAS,
        schemas: json,
        receivedAt: Date.now(),
    };
}

function fetchSchemas() {
    return dispatch => {
        dispatch(requestSchemas());
        return api.get(`/schema`).then(response => dispatch(receiveSchemas(response.data)));
    };
}

function shouldFetchSchemas(state) {
    if (Object.keys(state.schemas).length === 0) {
        return true;
    } else {
        return false;
    }
}

export function fetchSchemasIfNeeded() {
    return (dispatch, getState) => {
        if (shouldFetchSchemas(getState())) {
            return dispatch(fetchSchemas());
        }
    };
}
