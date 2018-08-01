import fetch from "cross-fetch";

const apiUrl = window.location.protocol + "//" + window.location.host + "/api";

export const REQUEST_EFFECT_LIST = "REQUEST_EEFECT_LIST";
export const RECEIVE_EFFECT_LIST = "RECEIVE_EFFECT_LIST";

function requestEffectList() {
  return {
    type: REQUEST_EFFECT_LIST
  };
}

function receiveEffectList(json) {
  return {
    type: RECEIVE_EFFECT_LIST,
    effects: json.effects,
    receivedAt: Date.now()
  };
}

function fetchEffectList() {
  return dispatch => {
    dispatch(requestEffectList());
    return fetch(`${apiUrl}/schema/effects`)
      .then(response => response.json())
      .then(json => dispatch(receiveEffectList(json)));
  };
}

function shouldFetchEffectList(state) {
  if (Object.keys(state.effects).length === 0) {
    return true;
  } else {
    return false;
  }
}

export function fetchEffectListIfNeeded() {
  return (dispatch, getState) => {
    if (shouldFetchEffectList(getState())) {
      return dispatch(fetchEffectList());
    }
  };
}
