import fetch from "cross-fetch";

const apiUrl = window.location.protocol + "//" + window.location.host + "/api";

export const ADD_SCENE = "ADD_SCENE"
export const DELETE_SCENE = "DELETE_SCENE"
export const GET_SCENES = "GET_SCENES"
export const ACTIVATE_SCENE = "ACTIVATE_SCENE"
export const RENAME_SCENE = "RENAME_SCENE"

export function addScene(name) {
  return dispatch => {
    const data = {
      name: name
    };
    return fetch(`${apiUrl}/scenes`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(data)
    })
      .then(response => response.json())
      .then(json => dispatch({
        type: ADD_SCENE,
        response: json
      }))
      .then(() => dispatch(getScenes()))
  };
}

export function deleteScene(id) {
  return dispatch => {
    const data = {
      id: id
    };
    return fetch(`${apiUrl}/scenes`, {
      method: "DELETE",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(data)
    })
      .then(response => response.json())
      .then(json => dispatch({
        type: DELETE_SCENE,
        response: json
      }))
      .then(() => dispatch(getScenes()))
  };
}

export function activateScene(id) {
  return dispatch => {
    const data = {
      id: id,
      action: 'activate'
    };
    fetch(`${apiUrl}/scenes`, {
      method: "PUT",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(data)
    })
      .then(response => response.json())
      .then(json => dispatch({
        type: ACTIVATE_SCENE,
        response: json
      }));
  };
}

export function renameScene(id, name) {
  return dispatch => {
    const data = {
      id: id,
      action: 'rename',
      name: name
    };
    fetch(`${apiUrl}/scenes`, {
      method: "PUT",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(data)
    })
      .then(response => response.json())
      .then(json => dispatch({
        type: RENAME_SCENE,
        response: json
      }));
  };
}


export function getScenes() {
  return dispatch => {
    fetch(`${apiUrl}/scenes`, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
    })
      .then(response => response.json())
      .then(json => dispatch({
          type: GET_SCENES,
          scenes: json.scenes,
          receivedAt: Date.now()
      }))
  }
}
