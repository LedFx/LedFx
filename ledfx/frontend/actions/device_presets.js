import fetch from "cross-fetch";

const apiUrl = window.location.protocol + "//" + window.location.host + "/api";

export const ACTIVATE_PRESET = "ACTIVATE_PRESET"
export const GET_PRESETS = "GET_PRESETS"
export const SAVE_PRESET = "SAVE_PRESET"

export function activatePreset(deviceId, category, effectId, presetId) {
  return dispatch => {
    const data = {
      category: category,
      effect_id: effectId,
      preset_id: presetId,
    };
    fetch(`${apiUrl}/devices/${deviceId}/presets`, {
      method: "PUT",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(data)
    })
      .then(response => response.json())
      .then(json => dispatch({
        type: ACTIVATE_PRESET,
        response: json
      }));
  };
}

export function savePreset(deviceId, name) {
  return dispatch => {
    const data = {
      preset_name: name,
    };
    fetch(`${apiUrl}/devices/${deviceId}/presets`, {
      method: "PUT",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(data)
    })
      .then(response => response.json())
      .then(json => dispatch({
        type: RENAME_PRESET,
        response: json
      }));
  };
}


export function getPresets(deviceId) {
  return dispatch => {
    fetch(`${apiUrl}/devices/${deviceId}/presets`, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
    })
      .then(response => response.json())
      .then(json => dispatch({
          type: GET_PRESETS,
          presets: json.presets,
          receivedAt: Date.now()
      }))
  };
}