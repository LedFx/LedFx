import { createAction, handleActions } from 'redux-actions';
import * as displayProxies from 'proxies/display';
// import { updateDisplays } from './settings';
import { showdynSnackbar } from './ui';
// Actions
const ACTION_ROOT = 'displays';

export const displaysRequested = createAction(`${ACTION_ROOT}/DISPLAYS_REQUESTED`);
export const deleteSegment = createAction(`${ACTION_ROOT}/DISPLAY_DELETE_SEGMENT`);
export const handleSegmentChange = createAction(`${ACTION_ROOT}/DISPLAY_HANDLE_SEGMENTS`);
export const orderSegmentChange = createAction(`${ACTION_ROOT}/DISPLAY_ORDER_SEGMENTS`);
export const displaysReceived = createAction(`${ACTION_ROOT}/DISPLAYS_RECEIVED`);
export const displayUpdated = createAction(`${ACTION_ROOT}/DISPLAY_UPDATED`);
export const scanProgressUpdated = createAction(`${ACTION_ROOT}/DISPLAY_SCAN_PROGRESS_UPDATED`);

// Reducer
const INITIAL_STATE = {
    isLoading: false,
    scanProgress: 0,
    list: [],
};

export default handleActions(
    {
        [deleteSegment]: (state, { payload }) => {
            const { displayId, segIndex } = payload;
            const newState = {
                ...state,
                list: state.list.map(reduxItem => {
                    if (reduxItem.id === displayId) {
                        reduxItem.segments = [
                            ...reduxItem.segments.slice(0, segIndex),
                            ...reduxItem.segments.slice(segIndex + 1),
                        ];
                    }
                    return reduxItem;
                }),
            };
            return newState;
        },
        [handleSegmentChange]: (state, { payload }) => {
            const { displayId, newValue, segIndex, invert } = payload;
            const newState = {
                ...state,
                list: state.list.map(reduxItem => {
                    if (reduxItem.id === displayId) {
                        if (newValue) {
                            reduxItem.segments[segIndex][1] = newValue[0];
                            reduxItem.segments[segIndex][2] = newValue[1];
                        }
                        if (invert) {
                            reduxItem.segments[segIndex][3] = !reduxItem.segments[segIndex][3];
                        }
                    }
                    return reduxItem;
                }),
            };
            return newState;
        },
        [orderSegmentChange]: (state, { payload }) => {
            const { displayId, segIndex, order } = payload;
            const newState = {
                ...state,
                list: state.list.map(reduxItem => {
                    if (reduxItem.id === displayId) {
                        let data = [...reduxItem.segments];

                        if (order === 'UP') {
                            let temp = data[segIndex - 1];
                            data[segIndex - 1] = data[segIndex];
                            data[segIndex] = temp;

                            reduxItem.segments = data;
                        }
                        if (order === 'DOWN') {
                            let temp = data[segIndex + 1];
                            data[segIndex + 1] = data[segIndex];
                            data[segIndex] = temp;

                            reduxItem.segments = data;
                        }
                    }
                    return reduxItem;
                }),
            };
            return newState;
        },
        [displaysRequested]: state => ({
            ...state,
            isLoading: true,
        }),
        [scanProgressUpdated]: (state, { payload }) => ({
            ...state,
            scanProgress: payload,
        }),
        [displaysReceived]: (state, { payload, error }) => ({
            ...state,
            list: error ? state.list : convertDisplaysDictionaryToList(payload),
            dictionary: error ? state.dictionary : payload,
            isLoading: false,
            error: error ? payload.message : '',
        }),
        [displayUpdated]: (state, { payload, payload: { id, ...data }, error }) => {
            const updatedDisplays = {
                ...state.dictionary,
                [id]: {
                    ...state.dictionary[id],
                    ...data,
                },
            };
            return {
                ...state,
                list: error ? state.list : convertDisplaysDictionaryToList(updatedDisplays),
                dictionary: error ? state.dictionary : updatedDisplays,
                error: error ? payload.mesasge : '',
            };
        },
    },
    INITIAL_STATE
);

export function fetchDisplayList() {
    return async dispatch => {
        dispatch(displaysRequested());
        try {
            const response = await displayProxies.getDisplays();
            if (response.statusText === 'OK') {
                const { displays } = response.data;
                Object.keys(displays).forEach(key => {
                    const data = displays[key];
                    data.effect.active = !!data.effect.name;
                });
                dispatch(displaysReceived(displays));
                // dispatch(updateDisplays(convertDisplaysDictionaryToList(displays)));
            }
        } catch (error) {
            dispatch(displaysReceived(error));
        }
    };
}

export function addDisplay(config) {
    return async dispatch => {
        const data = config;
        try {
            const response = await displayProxies.createDisplay(data);
            if (response.statusText === 'OK') {
                dispatch(fetchDisplayList());
            }
        } catch (error) {
            console.log('Error adding display', error.message);
        }
    };
}

// const sleep = ms => {
//     return new Promise(resolve => setTimeout(resolve, ms));
// };

export function findWLEDDisplays({ resolve, reject }) {
    return async dispatch => {
        try {
            // const response = await displayProxies.scanForDisplays();
            // if (response.statusText === 'OK') {
            //     for (let sec = 1; sec <= 10; sec++) {
            //         await sleep(1000).then(() => {
            //             dispatch(fetchDisplayList());
            //             dispatch(scanProgressUpdated(sec));
            //         });
            //     }
            //     resolve();
            //     dispatch(scanProgressUpdated(0));
            // }
        } catch (error) {
            console.log('WLED display scan failed', error.message);
            reject(error.message);
        }
    };
}

export function updateDisplayConfig({ id, data }) {
    console.log(id, data);
    return async dispatch => {
        try {
            const response = await displayProxies.updateDisplaySegments(id, {
                segments: [...data],
            });
            if (response.statusText === 'OK') {
                dispatch(fetchDisplayList());
            }
        } catch (error) {
            console.log('Error updating display', error.message);
        }
    };
}
// export function updateDisplayConfig(id, type, config) {
//     return async dispatch => {
//         try {
//             const response = await displayProxies.updateDisplaySegments(id, {
//                 config: { ...config, type },
//             });
//             if (response.statusText === 'OK') {
//                 dispatch(fetchDisplayList());
//             }
//         } catch (error) {
//             console.log('Error updating display', error.message);
//         }
//     };
// }

export function setDisplayEffect(id, data) {
    return async (dispatch, getState) => {
        const display = getState().displays.dictionary[id];
        try {
            dispatch(
                displayUpdated({
                    id,
                    ...display,
                    effect: { ...display.effect, isProcessing: true },
                })
            );

            const response = await displayProxies.setDisplayEffect(id, {
                type: data.type || 'wavelength(Reactive)',
                config: data,
            });

            dispatch(
                displayUpdated({
                    id,
                    effect: { ...data, ...response.data.effect, isProcessing: false },
                })
            );
            dispatch(showdynSnackbar('Success!'));
        } catch (error) {
            displayUpdated(error);
        }
    };
}

export function handleActiveDisplayEffect(id, payload) {
    return async (dispatch, getState) => {
        const display = getState().displays.dictionary[id];
        if (display)
            dispatch(
                displayUpdated({ id, ...display, effect: { ...display.effect, active: payload } })
            );
    };
}

export function clearDisplayEffect(id) {
    return async (dispatch, getState) => {
        const display = getState().displays.dictionary[id];
        try {
            dispatch(
                displayUpdated({
                    id,
                    ...display,
                    effect: { ...display.effect, isProcessing: true },
                })
            );

            await displayProxies.deleteDisplayEffect(id);
            dispatch(
                displayUpdated({
                    id,
                    effect: { ...display.effect, active: false, isProcessing: false },
                })
            );
        } catch (error) {
            displayUpdated(error);
        }
    };
}

export function deleteDisplay(id) {
    return async dispatch => {
        try {
            const response = await displayProxies.deleteDisplay(id);
            if (response.statusText === 'OK') {
                dispatch(fetchDisplayList());
            }
        } catch (error) {
            console.log('Error deleting display', error.message);
        }
    };
}

const convertDisplaysDictionaryToList = (displays = {}) =>
    Object.keys(displays).map(key => {
        const currentDisplay = displays[key];
        return {
            ...currentDisplay,
            key,
            id: key,
            name: currentDisplay.config.name,
        };
    });
