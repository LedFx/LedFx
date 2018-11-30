import fetch from "cross-fetch";

const apiUrl = window.location.protocol + "//" + window.location.host + "/api";

export const REQUEST_SCHEMAS = "REQUEST_SCHEMAS";
export const RECEIVE_SCHEMAS = "RECEIVE_SCHEMAS";

function requestSchemas() {
  return {
    type: REQUEST_SCHEMAS
  };
}

function receiveSchemas(json) {
  return {
    type: RECEIVE_SCHEMAS,
    schemas: json,
    receivedAt: Date.now()
  };
}

function fetchSchemas() {
  return dispatch => {
    dispatch(requestSchemas());
    return fetch(`${apiUrl}/schema`)
      .then(response => response.json())
      .then(json => dispatch(receiveSchemas(json)));
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
