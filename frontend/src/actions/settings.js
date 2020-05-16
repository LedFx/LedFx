const apiUrl = window.location.protocol + "//" + window.location.host + "/api";

export const GET_AUDIO_INPUTS = "GET_AUDIO_INPUTS"
export const SET_AUDIO_INPUT = "GET_AUDIO_INPUT"

export function setAudioDevice(index) {
  return dispatch => {
    const data = {
      index: parseInt(index)
    };
    fetch(`${apiUrl}/audio/devices`, {
      method: "PUT",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(data)
    })
      .then(response => response.json())
      .then(json => dispatch({
        type: SET_AUDIO_INPUT,
        response: json
      }))
      .then(() => dispatch(getAudioDevices()));
  };
}


export function getAudioDevices() {
  return dispatch => {
    fetch(`${apiUrl}/audio/devices`, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
    })
      .then(response => response.json())
      .then(json => dispatch({
          type: GET_AUDIO_INPUTS,
          audioDevices: json,
          receivedAt: Date.now()
      }))
  }
}
