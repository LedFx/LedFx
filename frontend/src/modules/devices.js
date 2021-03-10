import { createAction, handleActions } from 'redux-actions';
import * as deviceProxies from 'proxies/device';
// import * as displayModules from 'modules/displays';
import { updateDevices } from './settings';
import { showdynSnackbar } from './ui';
// Actions
const ACTION_ROOT = 'devices';

export const devicesRequested = createAction(`${ACTION_ROOT}/DEVICES_REQUESTED`);
export const devicesReceived = createAction(`${ACTION_ROOT}/DEVICES_RECEIVED`);
export const deviceUpdated = createAction(`${ACTION_ROOT}/DEVICE_UPDATED`);
export const scanProgressUpdated = createAction(`${ACTION_ROOT}/DEVICE_SCAN_PROGRESS_UPDATED`);

// Reducer
const INITIAL_STATE = {
    isLoading: false,
    list: [],
    dictionary: {},
    scanProgress: 0,
};

export default handleActions(
    {
        [devicesRequested]: state => ({
            ...state,
            isLoading: true,
        }),
        [scanProgressUpdated]: (state, { payload }) => ({
            ...state,
            scanProgress: payload,
        }),
        [devicesReceived]: (state, { payload, error }) => ({
            ...state,
            list: error ? state.list : convertDevicesDictionaryToList(payload),
            dictionary: error ? state.dictionary : payload,
            isLoading: false,
            error: error ? payload.message : '',
        }),
        [deviceUpdated]: (state, { payload, payload: { id, ...data }, error }) => {
            const updatedDevices = {
                ...state.dictionary,
                [id]: {
                    ...state.dictionary[id],
                    ...data,
                },
            };
            return {
                ...state,
                list: error ? state.list : convertDevicesDictionaryToList(updatedDevices),
                dictionary: error ? state.dictionary : updatedDevices,
                error: error ? payload.message : '',
            };
        },
    },
    INITIAL_STATE
);

export function fetchDeviceList() {
    return async dispatch => {
        dispatch(devicesRequested());
        try {
            const response = await deviceProxies.getDevices();

            if (response.statusText === 'OK') {
                const { devices } = response.data;
                // console.log(devices);
                Object.keys(devices).forEach(key => {
                    const data = devices[key];

                    data.effect = { active: false };
                });
                // console.log('WTF', devices);
                dispatch(devicesReceived(devices));
                dispatch(updateDevices(convertDevicesDictionaryToList(devices)));
            }
        } catch (error) {
            dispatch(devicesReceived(error));
        }
    };
}

export function addDevice(type, config) {
    return async dispatch => {
        const data = {
            type: type,
            config: config,
        };
        try {
            const response = await deviceProxies.createDevice(data);
            if (response.statusText === 'OK') {
                dispatch(fetchDeviceList());
            }
        } catch (error) {
            console.log('Error adding device', error.message);
        }
    };
}

const sleep = ms => {
    return new Promise(resolve => setTimeout(resolve, ms));
};

export function findWLEDDevices({ resolve, reject }) {
    return async dispatch => {
        try {
            const response = await deviceProxies.scanForDevices();
            if (response.statusText === 'OK') {
                for (let sec = 1; sec <= 10; sec++) {
                    await sleep(1000).then(() => {
                        dispatch(fetchDeviceList());
                        // dispatch(displayModules.fetchDiplayList());
                        dispatch(scanProgressUpdated(sec));
                    });
                }
                resolve();
                dispatch(scanProgressUpdated(0));
            }
        } catch (error) {
            console.log('WLED device scan failed', error.message);
            reject(error.message);
        }
    };
}

export function updateDeviceConfig(id, type, config) {
    return async dispatch => {
        try {
            const response = await deviceProxies.updateDevice(id, {
                config: { ...config, type },
            });
            if (response.statusText === 'OK') {
                dispatch(fetchDeviceList());
            }
        } catch (error) {
            console.log('Error adding device', error.message);
        }
    };
}

export function setDeviceEffect(id, data) {
    return async (dispatch, getState) => {
        const device = getState().devices.dictionary[id];
        try {
            dispatch(
                deviceUpdated({ id, ...device, effect: { ...device.effect, isProcessing: true } })
            );

            const response = await deviceProxies.setDeviceEffect(id, {
                type: data.type || 'wavelength(Reactive)',
                config: data,
            });

            dispatch(
                deviceUpdated({
                    id,
                    effect: { ...data, ...response.data.effect, isProcessing: false },
                })
            );
            dispatch(showdynSnackbar('Success!'));
        } catch (error) {
            deviceUpdated(error);
        }
    };
}

export function handleActiveDeviceEffect(id, payload) {
    return async (dispatch, getState) => {
        const device = getState().devices.dictionary[id];
        if (device)
            dispatch(
                deviceUpdated({ id, ...device, effect: { ...device.effect, active: payload } })
            );
    };
}

export function clearDeviceEffect(id) {
    return async (dispatch, getState) => {
        const device = getState().devices.dictionary[id];
        try {
            dispatch(
                deviceUpdated({ id, ...device, effect: { ...device.effect, isProcessing: true } })
            );

            await deviceProxies.deleteDeviceEffect(id);
            dispatch(
                deviceUpdated({
                    id,
                    effect: { ...device.effect, active: false, isProcessing: false },
                })
            );
        } catch (error) {
            deviceUpdated(error);
        }
    };
}

export function deleteDevice(id) {
    return async dispatch => {
        try {
            const response = await deviceProxies.deleteDevice(id);
            if (response.statusText === 'OK') {
                dispatch(fetchDeviceList());
            }
        } catch (error) {
            console.log('Error deleting device', error.message);
        }
    };
}

const convertDevicesDictionaryToList = (devices = {}) =>
    Object.keys(devices).map(key => {
        const currentDevice = devices[key];
        return {
            ...currentDevice,
            key,
            id: key,
            name: currentDevice.config.name,
        };
    });
