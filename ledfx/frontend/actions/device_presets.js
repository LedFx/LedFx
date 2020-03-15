import fetch from "cross-fetch";

const apiUrl = window.location.protocol + "//" + window.location.host + "/api";

// CONSTANT device categories
export const DEFAULT_CAT = "default_presets"
export const CUSTOM_CAT = "custom_presets"

export const ACTIVATE_PRESET = "ACTIVATE_PRESET"
export const GET_DEVICE_PRESETS = "GET_DEVICE_PRESETS"
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

/**
 * Return the device's active effect's presets
 * Used in device view to switch presets
 */
export function getDevicePresets(deviceId) {
  return dispatch => {
    fetch(`${apiUrl}/devices/${deviceId}/presets`, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      }
    }).then(response => response.json())
    .then(json => dispatch({
      type: GET_DEVICE_PRESETS,
      presets: {
        customPresets: json.custom_presets,
        defaultPresets: json.default_presets
      }
    }))
  }
}
